from PIL import Image, ImageEnhance, ImageChops
import numpy as np
import colorsys

def sort_colors(colors, method="Luminance"):
    """
    Sorts a list of RGB tuples (0-255).
    Methods: "Luminance", "Hue", "Original"
    """
    if method == "Original" or not colors:
        return colors

    if method == "Luminance":
        # Relative luminance formula (ordered by brightness, descending)
        return sorted(colors, key=lambda c: (0.2126*c[0] + 0.7152*c[1] + 0.0722*c[2]), reverse=True)
    
    if method == "Hue":
        # Sort by Hue in HSV space
        return sorted(colors, key=lambda c: colorsys.rgb_to_hsv(c[0]/255.0, c[1]/255.0, c[2]/255.0)[0])
    
    return colors

def export_as_gpl(path, colors, name="Pixlato Export"):
    """
    Exports a list of RGB tuples as a GIMP Palette (.gpl) file.
    """
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write("GIMP Palette\n")
            f.write(f"Name: {name}\n")
            f.write("Columns: 0\n")
            f.write("#\n")
            for i, (r, g, b) in enumerate(colors):
                f.write(f"{r:>3} {g:>3} {b:>3}\tIndex {i}\n")
        return True
    except Exception as e:
        print(f"Error exporting GPL: {e}")
        return False

def extract_aesthetic_palette(img, color_count=16, w_sat=0.4, w_con=0.3, w_rar=0.3):
    """
    Optimized Weighted Extraction: Scores pixels by Saturation, Contrast, and Uniqueness.
    Uses downsampling for analysis speed and vectorized operations.
    """
    # 1. Performance Optimization: Resize for analysis if image is large
    # Palette extraction doesn't need 4K resolution. 256px is plenty.
    analysis_size = 256
    if max(img.size) > analysis_size:
        img_analysis = img.resize((analysis_size, analysis_size), resample=Image.LANCZOS)
    else:
        img_analysis = img

    img_rgb = img_analysis.convert("RGB")
    arr = np.array(img_rgb).astype(np.float32) / 255.0
    pixels = arr.reshape(-1, 3)
    
    # 2. Vectorized Scoring Components
    # Saturation (max - min)
    c_max = np.max(pixels, axis=1)
    c_min = np.min(pixels, axis=1)
    sats = c_max - c_min
    
    # Brightness (Value)
    vals = c_max
    
    # Contrast Score: High weight for very bright or dark
    contrast = np.abs(vals - 0.5) * 2.0
    
    # Uniqueness (Vectorized Hue Calculation)
    # Simplified Hue calculation: (G-B)/(max-min) etc.
    diff = sats + 1e-6
    r, g, b = pixels[:, 0], pixels[:, 1], pixels[:, 2]
    
    h = np.zeros_like(r)
    idx_r = (c_max == r)
    h[idx_r] = (g[idx_r] - b[idx_r]) / diff[idx_r]
    idx_g = (c_max == g)
    h[idx_g] = 2.0 + (b[idx_g] - r[idx_g]) / diff[idx_g]
    idx_b = (c_max == b)
    h[idx_b] = 4.0 + (r[idx_b] - g[idx_b]) / diff[idx_b]
    h = (h / 6.0) % 1.0
    
    h_hist, _ = np.histogram(h, bins=36, range=(0, 1))
    rarity = 1.0 / (h_hist[np.clip((h * 36).astype(int), 0, 35)] + 1.0)
    rarity = rarity / (np.max(rarity) + 1e-6)
    
    # 3. Final Importance Score with User Weights
    scores = (sats * w_sat) + (contrast * w_con) + (rarity * w_rar)
    
    # 4. Selection with Suppression (to ensure variety)
    selected_indices = []
    current_scores = scores.copy()
    
    # Limit candidates to speed up suppression loop if needed
    # (But with 256x256=65k pixels, it's already fast enough)
    for _ in range(color_count):
        best_idx = np.argmax(current_scores)
        if current_scores[best_idx] <= 0: break
        
        best_color = pixels[best_idx]
        selected_indices.append(best_idx)
        
        # Suppress nearby colors in RGB space
        # Using squared distance for speed
        sq_diffs = np.sum((pixels - best_color)**2, axis=1)
        # Suppress everything within 0.15 distance (0.0225 squared)
        suppression = np.clip(sq_diffs / 0.0225, 0, 1)
        current_scores *= suppression
        
    res_rgb = [(int(p[0]*255), int(p[1]*255), int(p[2]*255)) for p in pixels[selected_indices]]
    return res_rgb

def map_to_palette_perceptual(img, palette_img):
    """
    Maps image to a palette using perceptual weights (emphasizing Saturation and Value).
    """
    # Pillow's quantize already uses a decent perceptual model, 
    # but we can enhance it by boosting image saturation before mapping.
    enhancer = ImageEnhance.Color(img)
    perceptual_boosted = enhancer.enhance(1.2) # Boost saturation by 20% during mapping
    return perceptual_boosted.quantize(palette=palette_img, dither=Image.Dither.NONE)

def apply_palette_unified(img, palette_name="Original", custom_colors=None, dither=True, 
                          extract_policy="Standard", mapping_policy="Classic",
                          w_sat=0.4, w_con=0.3, w_rar=0.3):
    """
    Updated Pipeline supporting Weighted extraction and Perceptual mapping.
    """
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    alpha_mask = img.split()[-1]
    
    if palette_name == "Original":
        return img

    rgb_img = img.convert("RGB")

    # [Step 2 & 3] Target Generation
    target_palette = None
    is_low_color = False
    
    if palette_name == "Limited":
        if extract_policy == "Aesthetic":
            colors = extract_aesthetic_palette(rgb_img, custom_colors if isinstance(custom_colors, int) else 16,
                                              w_sat=w_sat, w_con=w_con, w_rar=w_rar)
            # Create palette image from custom list
            flat = []
            for c in colors: flat.extend(c)
            flat += [0] * (768 - len(flat))
            target_palette = Image.new("P", (1, 1))
            target_palette.putpalette(flat)
            is_low_color = len(colors) <= 4
        else:
            # Standard Pillow extraction
            num = custom_colors if isinstance(custom_colors, int) else 256
            target_palette = rgb_img.quantize(colors=num, dither=Image.Dither.NONE)
            is_low_color = num <= 4
    else:
        target_palette, is_low_color = _generate_target_palette(palette_name, custom_colors)
    
    if dither and is_low_color:
        rgb_img = _apply_pre_contrast(rgb_img, factor=1.15)

    # [Step 4] Unified Quantization
    if target_palette:
        dither_method = Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE
        
        if mapping_policy == "Perceptual":
            # Use saturation-boosted mapping
            enhancer = ImageEnhance.Color(rgb_img)
            mapping_src = enhancer.enhance(1.2)
            quantized_img = mapping_src.quantize(palette=target_palette, dither=dither_method)
        else:
            quantized_img = rgb_img.quantize(palette=target_palette, dither=dither_method)
            
        result_rgb = quantized_img.convert("RGB")
        
    elif palette_name == "Custom_16bit":
        arr = np.array(rgb_img).astype(np.int16)
        arr = (arr // 16) * 17
        result_rgb = Image.fromarray(arr.astype(np.uint8))
        
    elif palette_name == "Grayscale":
         num_colors = custom_colors if isinstance(custom_colors, int) else 256
         dither_method = Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE
         result_rgb = rgb_img.convert("L").quantize(colors=num_colors, dither=dither_method).convert("RGB")
         
    else:
         result_rgb = rgb_img.convert("RGB")

    result_rgb.putalpha(alpha_mask)
    return result_rgb

def _generate_target_palette(palette_name, custom_colors):
    """
    Generates a 'P' mode image containing the strict target palette.
    Returns: (palette_image, is_low_color_bool)
    """
    
    colors = []
    is_low_color = False
    
    # 1. Preset Palettes
    presets = {
        "GameBoy": [(15, 56, 15), (48, 98, 48), (139, 172, 15), (155, 188, 15)],
        "CGA": [(0, 0, 0), (85, 255, 255), (255, 85, 255), (255, 255, 255)],
        "Pico-8": [
            (0,0,0), (29,43,83), (126,37,83), (0,135,81),
            (171,82,54), (95,87,79), (194,195,199), (255,241,232),
            (255,0,77), (255,163,0), (255,236,39), (0,228,54),
            (41,173,255), (131,118,156), (255,119,168), (255,204,170)
        ]
    }
    
    if palette_name in presets:
        colors = presets[palette_name]
        is_low_color = len(colors) <= 4
        
    elif palette_name == "Custom_User" and custom_colors:
        # custom_colors is a list of tuples [(r,g,b), ...]
        colors = custom_colors
        # Remove any potential black padding if it wasn't intended (though UI usually handles this)
        # But we need to keep 16 slots if that was the intent.
        # Actually, strict mapping allows unused slots.
        is_low_color = len(colors) <= 4
        
    elif palette_name == "Grayscale":
        # Generate N-step grayscale palette
        steps = custom_colors if isinstance(custom_colors, int) else 4
        if steps < 2: steps = 2
        # Create linear gradient from 0 to 255
        vals = np.linspace(0, 255, steps, dtype=int)
        colors = [(v, v, v) for v in vals]
        is_low_color = steps <= 4
        
    elif palette_name == "Custom_16bit":
        # Cannot be represented by a fixed small palette easily due to 4096 combinations.
        # This requires algorithmic quantization, not palette mapping.
        return None, False
        
    elif palette_name == "Limited":
        # Adaptive, no fixed palette
        return None, False

    if not colors:
        return None, False

    # Create master palette image
    # Flatten list of tuples -> list of ints
    flat_palette = [c for rgb in colors for c in rgb]
    
    # Pad to 768 integers (256 colors * 3)
    # Important: Fill unused slots with the last color or repeat to avoid accidental mapping to black 0,0,0
    # if 0,0,0 is not in the palette. But Pillow treats unset as 0,0,0.
    # Safe bet: Pad with the first color to avoid 'black hole' effect for unassigned indices,
    # OR let them be 0 if 0 is not used.
    padding = (768 - len(flat_palette))
    flat_palette += [0] * padding
    
    pal_img = Image.new("P", (1, 1))
    pal_img.putpalette(flat_palette)
    
    return pal_img, is_low_color

def _apply_pre_contrast(img, factor=1.15):
    """
    Boosts contrast of the image.
    Used to pre-separate dark and light areas before aggressive dithering.
    """
    enhancer = ImageEnhance.Contrast(img)
    return enhancer.enhance(factor)
