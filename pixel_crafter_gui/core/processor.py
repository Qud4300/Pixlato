from PIL import Image, ImageFilter
import numpy as np

# Security: Prevent decompression bomb attacks by limiting max pixels (e.g., 100MP)
Image.MAX_IMAGE_PIXELS = 100_000_000 

def enhance_internal_edges(img, sensitivity=1.0):
    """
    Applies Unsharp Mask to enhance internal edges/details before downsampling.
    This helps preserve features like eyes, nose, mouth during pixelation.
    
    Args:
        img (Image): PIL Image (RGBA).
        sensitivity (float): Edge enhancement strength (0.0 to 2.0).
                            0.0 = No enhancement, 2.0 = Maximum enhancement.
    Returns:
        Image: Enhanced image.
    """
    if sensitivity <= 0:
        return img
    
    # Unsharp Mask parameters scale with sensitivity
    # radius: controls blur size (higher = more global contrast)
    # percent: controls intensity of sharpening
    # threshold: controls which edges are affected (lower = more edges)
    radius = 0.5 + (sensitivity * 0.75)  # 0.5 to 2.0
    percent = int(100 + (sensitivity * 75))  # 100 to 250
    threshold = max(1, int(5 - sensitivity * 2))  # 5 to 1
    
    enhanced = img.filter(ImageFilter.UnsharpMask(radius=radius, percent=percent, threshold=threshold))
    return enhanced

def remove_background(img, tolerance=50):
    """
    Removes the background color (detected from corners) by making it transparent.
    Uses floodfill from corners.
    """
    try:
        from PIL import ImageDraw
        img = img.convert("RGBA")
        width, height = img.size
        
        # Sample corners
        corners = [(0, 0), (width-1, 0), (0, height-1), (width-1, height-1)]
        
        # We fill from each corner
        # Using a relatively high tolerance by default (50) to catch JPEG artifacts if any,
        # but for pixel art 0 or 10 is better. Let's stick to 20 usually.
        # User doesn't control tolerance yet, so hardcode 40.
        
        # Need to verify if the corner is transparent already
        if img.getpixel((0,0))[3] == 0: return img

        # Floodfill with (0,0,0,0) - Transparent
        # Note: thresh requires PIL > 8.something.
        ImageDraw.floodfill(img, (0, 0), (0, 0, 0, 0), thresh=tolerance)
        
        # Check other corners if they are still opaque and match the "removed" color logic 
        # (visual check handles it, blindly flooding corners is safer if they are consistent)
        
        # Top-Right
        if img.getpixel((width-1, 0))[3] != 0:
             ImageDraw.floodfill(img, (width-1, 0), (0, 0, 0, 0), thresh=tolerance)
             
        # Bottom-Left
        if img.getpixel((0, height-1))[3] != 0:
             ImageDraw.floodfill(img, (0, height-1), (0, 0, 0, 0), thresh=tolerance)

        # Bottom-Right
        if img.getpixel((width-1, height-1))[3] != 0:
             ImageDraw.floodfill(img, (width-1, height-1), (0, 0, 0, 0), thresh=tolerance)
             
        return img
    except Exception as e:
        print(f"Background Remove Error: {e}")
        return img

def pixelate_image(image_path, pixel_size, target_width=None, edge_enhance=False, edge_sensitivity=1.0, downsample_method="Standard", remove_bg=False, bg_mode="None", bg_seeds=None, fg_seeds=None, plugin_engine=None, plugin_params=None):
    """
    Opens an image and reduces its resolution with advanced background removal.
    """
    try:
        # Open as RGBA
        img = Image.open(image_path).convert("RGBA")
    except Exception as e:
        print(f"Error opening image: {e}")
        return None

    # [Hook] PRE_PROCESS
    if plugin_engine:
        img = plugin_engine.execute_hook("PRE_PROCESS", img, plugin_params)

    # Apply Advanced Background Removal
    if bg_mode == "AI Auto":
        img = remove_background_ai(img)
    elif bg_mode == "Interactive" and bg_seeds:
        img = remove_background_interactive(img, bg_seeds, fg_seeds)
    elif bg_mode == "Classic" or remove_bg:
        img = remove_background(img, tolerance=40)

    # Apply edge enhancement if requested (before downsampling)
    if edge_enhance and edge_sensitivity > 0:
        img = enhance_internal_edges(img, edge_sensitivity)

    # [Hook] PRE_DOWNSAMPLE
    if plugin_engine:
        img = plugin_engine.execute_hook("PRE_DOWNSAMPLE", img, plugin_params)

    original_width, original_height = img.size
    
    if target_width:
        aspect_ratio = original_height / original_width
        small_width = target_width
        small_height = int(small_width * aspect_ratio)
    else:
        # Ensure at least 1x1
        small_width = max(1, original_width // pixel_size)
        small_height = max(1, original_height // pixel_size)

    # Select downsampling method
    if downsample_method == "K-Means":
        small_img = downsample_kmeans_adaptive(img, pixel_size, small_width, small_height)
    else:
        # Standard BOX
        small_img = img.resize((small_width, small_height), resample=Image.BOX)

    # [Hook] POST_DOWNSAMPLE
    if plugin_engine:
        small_img = plugin_engine.execute_hook("POST_DOWNSAMPLE", small_img, plugin_params)

    return small_img



def downsample_kmeans_adaptive(img, pixel_size, out_w, out_h):
    """
    Hardware-accelerated downsampling using PyTorch. 
    Vectorizes the K-Means logic across all blocks simultaneously.
    """
    try:
        import torch
    except ImportError:
        # Emergency fallback (should not happen in this Phase)
        return img.resize((out_w, out_h), resample=Image.BOX)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    # 1. Convert to float tensor
    arr = np.array(img.convert("RGBA"))
    h, w, _ = arr.shape
    img_tensor = torch.from_numpy(arr).to(device).float()
    
    # 2. Pad/Crop to exact required size for reshaping
    target_h, target_w = out_h * pixel_size, out_w * pixel_size
    img_tensor = img_tensor[:target_h, :target_w, :]
    
    # 3. Reshape to blocks: (out_h, out_w, ps, ps, 4)
    # Then permute to (B, N, 4) where B = out_h * out_w, N = ps * ps
    blocks = img_tensor.reshape(out_h, pixel_size, out_w, pixel_size, 4).permute(0, 2, 1, 3, 4)
    num_blocks = out_h * out_w
    block_pixels = blocks.reshape(num_blocks, -1, 4)
    
    rgb = block_pixels[..., :3]
    alpha = block_pixels[..., 3]
    
    # 4. Compute variance to identify high-detail blocks
    # Variance per block (sum of RGB variances)
    block_variances = torch.var(rgb, dim=1).sum(dim=1)
    
    # Initial Result: Compute basic mean for all blocks
    final_rgb = rgb.mean(dim=1)
    
    # 5. Adaptive K-Means for High Variance Blocks
    # Threshold for "High Detail" (Approx 40 in 0-255 scale)
    var_threshold = 40.0 * 3
    high_var_mask = block_variances > var_threshold
    
    if high_var_mask.any():
        hv_pixels = rgb[high_var_mask]  # (B_hv, N, 3)
        b_hv = hv_pixels.shape[0]
        
        # Initialize 2 clusters per block: Darkest and Brightest pixels
        lum = 0.299 * hv_pixels[...,0] + 0.587 * hv_pixels[...,1] + 0.114 * hv_pixels[...,2]
        c0_idx = lum.argmin(dim=1)
        c1_idx = lum.argmax(dim=1)
        
        batch_seq = torch.arange(b_hv, device=device)
        c0 = hv_pixels[batch_seq, c0_idx].unsqueeze(1) # (B_hv, 1, 3)
        c1 = hv_pixels[batch_seq, c1_idx].unsqueeze(1) # (B_hv, 1, 3)
        centers = torch.cat([c0, c1], dim=1)           # (B_hv, 2, 3)
        
        # Simple K-Means iteration (K=2)
        for _ in range(4):
            # Assign: Calculate distance to centers
            # dist shape: (B_hv, N, 2)
            dist = torch.cdist(hv_pixels, centers)
            labels = dist.argmin(dim=2) # (B_hv, N)
            
            # Update
            m0 = (labels == 0).float().unsqueeze(-1)
            m1 = (labels == 1).float().unsqueeze(-1)
            
            # Weighted mean update
            centers[:, 0] = (hv_pixels * m0).sum(dim=1) / m0.sum(dim=1).clamp(min=1)
            centers[:, 1] = (hv_pixels * m1).sum(dim=1) / m1.sum(dim=1).clamp(min=1)

        # Selection: Choose the cluster furthest from the block mean (Contrast Selection)
        hv_means = hv_pixels.mean(dim=1).unsqueeze(1)
        dist_to_mean = torch.norm(centers - hv_means, dim=2)
        best_cluster = dist_to_mean.argmax(dim=1)
        
        final_rgb[high_var_mask] = centers[batch_seq, best_cluster]

    # 6. Combine RGB with Avg Alpha
    final_alpha = alpha.mean(dim=1).unsqueeze(-1)
    result_tensor = torch.cat([final_rgb, final_alpha], dim=1)
    
    # 7. Back to PIL
    result_arr = result_tensor.reshape(out_h, out_w, 4).byte().cpu().numpy()
    return Image.fromarray(result_arr, "RGBA")

# Global session cache for rembg to avoid reloading the model
REMBG_SESSION = None

def remove_background_ai(img):
    """
    Uses rembg (AI model) to automatically extract the main subject.
    Utilizes GPU (CUDA) if available for maximum performance.
    """
    global REMBG_SESSION
    try:
        from rembg import remove, new_session
        import onnxruntime as ort
        
        # Initialize session if it doesn't exist
        if REMBG_SESSION is None:
            # Check for GPU providers
            providers = ort.get_available_providers()
            target_providers = []
            if 'CUDAExecutionProvider' in providers:
                target_providers.append('CUDAExecutionProvider')
            if 'CPUExecutionProvider' in providers:
                target_providers.append('CPUExecutionProvider')
            
            # Use u2net (standard) but we could use u2netp for even more speed if needed
            REMBG_SESSION = new_session(model_name="u2net", providers=target_providers)
            
        return remove(img, session=REMBG_SESSION)
    except Exception as e:
        print(f"AI Background Removal Error: {e}")
        return img

def remove_background_interactive(img, bg_seeds, fg_seeds=None):
    """
    Uses OpenCV GrabCut to interactively remove background based on user points.
    bg_seeds: list of (x, y) coordinates for background
    fg_seeds: list of (x, y) coordinates for foreground (optional)
    """
    try:
        import cv2
        # Convert PIL to CV2 format (RGB)
        img_np = np.array(img.convert("RGB"))
        img_cv = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        
        mask = np.zeros(img_cv.shape[:2], np.uint8)
        mask.fill(cv2.GC_PR_FGD) # Default to probably foreground
        
        # Apply seeds
        for x, y in bg_seeds:
            if 0 <= x < img.width and 0 <= y < img.height:
                cv2.circle(mask, (int(x), int(y)), 5, cv2.GC_BGD, -1)
        
        if fg_seeds:
            for x, y in fg_seeds:
                if 0 <= x < img.width and 0 <= y < img.height:
                    cv2.circle(mask, (int(x), int(y)), 5, cv2.GC_FGD, -1)
        
        # GrabCut variables
        bgdModel = np.zeros((1, 65), np.float64)
        fgdModel = np.zeros((1, 65), np.float64)
        
        if bg_seeds:
            cv2.grabCut(img_cv, mask, None, bgdModel, fgdModel, 5, cv2.GC_INIT_WITH_MASK)
        else:
            return img
            
        mask2 = np.where((mask == 2) | (mask == 0), 0, 1).astype('uint8')
        res_np = np.array(img.convert("RGBA"))
        res_np[..., 3] = mask2 * 255
        return Image.fromarray(res_np, "RGBA")
    except Exception as e:
        print(f"Interactive Background Removal Error: {e}")
        return img

def apply_grain_effect(img, intensity=15):
    """
    Adds film grain noise to the image.
    Uses Numpy for high performance.
    """
    if intensity <= 0:
        return img
        
    # Convert to RGBA
    img = img.convert("RGBA")
    arr = np.array(img).astype(np.float32)
    
    # Generate monochromatic noise
    # We apply the same noise to R, G, B to avoid color shifting
    noise = np.random.randint(-intensity, intensity + 1, size=(arr.shape[0], arr.shape[1], 1))
    
    # Apply noise to RGB channels only
    arr[..., :3] += noise
    
    # Clamp values
    arr[..., :3] = np.clip(arr[..., :3], 0, 255)
    
    return Image.fromarray(arr.astype(np.uint8), "RGBA")

def upscale_for_preview(small_img, original_size):
    """Upscales a small image to a larger size using NEAREST neighbor."""
    return small_img.resize(original_size, resample=Image.NEAREST)

def save_image(img, path):
    img.save(path)

def add_outline(img, color=(0, 0, 0, 255)):
    """
    Adds a 1-pixel outline around non-transparent pixels.
    Assumes 'img' is RGBA.
    """
    # Create a mask of non-transparent pixels
    # Alpha > 0 considered 'content'
    # We can use ImageFilter.MaxFilter(3) on the alpha channel to dilate it.
    
    img = img.convert("RGBA")
    r, g, b, a = img.split()
    
    # Binarize alpha: 0 or 255
    mask = a.point(lambda p: 255 if p > 0 else 0)
    
    # Dilate the mask (expand by 1 pixel)
    # MaxFilter(3) looks at 3x3 window, taking max value.
    # Center pixel gets 255 if any neighbor is 255.
    dilated_mask = mask.filter(ImageFilter.MaxFilter(3))
    
    # The outline is (Dilated - Original)
    # However, we want the outline to be *behind* the original pixels regarding transparency?
    # Usually outline is drawn *around*, so it expands the sprite. 
    # Or strict outline replacing border pixels?
    # Standard outline: New pixels at border.
    
    # Let's subtract original mask from dilated mask to find the "new" edge pixels.
    # PIL doesn't have direct subtract for images easily without numpy or ImageChops.
    from PIL import ImageChops
    outline_area = ImageChops.difference(dilated_mask, mask)
    
    # Ideally we just composite.
    # Paste the outline color where dilated_mask is white, then paste original image over it.
    
    # Create solid color image
    outline_img = Image.new("RGBA", img.size, color)
    
    # Create a new blank image
    result = Image.new("RGBA", img.size, (0,0,0,0))
    
    # Paste outline using dilated mask
    result.paste(outline_img, (0,0), mask=dilated_mask)
    
    # Paste original image over it (restoring original colors)
    result.paste(img, (0,0), mask=img)
    
    return result
