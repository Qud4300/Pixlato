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

def apply_palette_unified(img, palette_name="Original", custom_colors=None, dither=True):
    """
    Unified Pipeline for Palette Application.
    
    Stages:
    1. Standardization: RGBA conversion & Alpha extraction.
    2. Pre-processing: Adaptive contrast enhancement for low-color palettes.
    3. Target Generation: Create a standardized 'Master Palette' image.
    4. Quantization: Strict mapping to the master palette using Pillow's dither engine.
    5. Compositing: Restore Alpha and finalize.
    """
    
    # [Step 1] Standardization
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    
    # Extract Alpha Mask for final compositing
    alpha_mask = img.split()[-1]
    
    # Optimize: If palette is Original, skip processing but ensure RGBA
    if palette_name == "Original":
        return img

    # Work on RGB for processing
    rgb_img = img.convert("RGB")

    # [Step 2 & 3] Target Generation & Pre-processing
    target_palette, is_low_color = _generate_target_palette(palette_name, custom_colors)
    
    # Pre-contrast: If using dithering with low color count (e.g. Gameboy), boost contrast
    # to prevent "washed out" dark areas due to noise mixing.
    if dither and is_low_color:
        rgb_img = _apply_pre_contrast(rgb_img, factor=1.15) # 15% boost

    # [Step 4] Unified Quantization
    if target_palette:
        # Strict Mapping: Force mapping to the exact target palette
        dither_method = Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE
        quantized_img = rgb_img.quantize(palette=target_palette, dither=dither_method)
        result_rgb = quantized_img.convert("RGB")
        
    elif palette_name == "Custom_16bit":
        # Algorithmic 12-bit RGB (4-bit per channel) -> 4096 colors
        # This creates a retro "Amiga/ST" look.
        # Accuracy: (x // 16) * 17 maps 0-15 exactly to 0-255.
        arr = np.array(rgb_img).astype(np.int16)
        arr = (arr // 16) * 17
        result_rgb = Image.fromarray(arr.astype(np.uint8))
        
    elif palette_name == "Grayscale":
         # Fallback for dynamic grayscale
         num_colors = custom_colors if isinstance(custom_colors, int) else 256
         dither_method = Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE
         # For grayscale, we first convert to L, then quantize with dither
         result_rgb = rgb_img.convert("L").quantize(colors=num_colors, dither=dither_method).convert("RGB")
         
    else:
         # Generic Fallback (Limited Mode)
         num_colors = custom_colors if isinstance(custom_colors, int) else 256
         dither_method = Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE
         
         if dither:
             # To ensure we use EXACTLY the limited colors during dithering:
             # 1. Generate the best palette first (no dither)
             temp_pal = rgb_img.quantize(colors=num_colors, dither=Image.Dither.NONE)
             # 2. Apply it with dither
             result_rgb = rgb_img.quantize(palette=temp_pal, dither=dither_method).convert("RGB")
         else:
             result_rgb = rgb_img.quantize(colors=num_colors, dither=Image.Dither.NONE).convert("RGB")

    # [Step 5] Compositing - Restore Alpha
    # We use the original alpha mask to cut out the background
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
