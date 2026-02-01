
import os
import sys
from PIL import Image

# Add core path
sys.path.append(os.path.join(os.getcwd(), 'pixel_crafter_gui'))

from core.processor import pixelate_image
from core.palette import apply_palette_unified

def process():
    source_path = r'temp_image\pixlato_logic_overlap_logo_v2.png'
    output_dir = r'temp_image\outputs'
    
    if not os.path.exists(source_path):
        print(f"Source not found: {source_path}")
        return

    img = Image.open(source_path).convert("RGBA")
    w, h = img.size
    pixel_size = 2
    
    # Common parameters for apply_palette_unified
    palette_params = {
        "dither": False,
        "extract_policy": "Standard",
        "mapping_policy": "Perceptual", # Using the new LAB mapping
        "w_sat": 0.4, "w_con": 0.3, "w_rar": 0.3
    }

    # 1. Original Palette
    print("Generating: original_palette.png")
    small = img.resize((w // pixel_size, h // pixel_size), Image.NEAREST)
    res1 = small.resize((w, h), Image.NEAREST)
    res1.save(os.path.join(output_dir, "original_palette.png"))

    # 2. Limited (256 colors)
    print("Generating: limited_256.png")
    pal_img = apply_palette_unified(img, palette_name="Limited", custom_colors=256, **palette_params)
    small_pal = pal_img.resize((w // pixel_size, h // pixel_size), Image.NEAREST)
    res2 = small_pal.resize((w, h), Image.NEAREST)
    res2.save(os.path.join(output_dir, "limited_256.png"))

    # 3. 16-bit (4096 colors)
    print("Generating: 16bit_4096.png")
    pal_img_16 = apply_palette_unified(img, palette_name="Custom_16bit", **palette_params)
    small_16 = pal_img_16.resize((w // pixel_size, h // pixel_size), Image.NEAREST)
    res3 = small_16.resize((w, h), Image.NEAREST)
    res3.save(os.path.join(output_dir, "16bit_4096.png"))

    # 4. Auto Optimal (New Phase 48)
    print("Generating: auto_optimal_result.png")
    # Auto Optimal usually works best without dithering for solid areas
    pal_img_auto = apply_palette_unified(img, palette_name="Limited", dither=False, auto_optimal=True)
    small_auto = pal_img_auto.resize((w // pixel_size, h // pixel_size), Image.NEAREST)
    res4 = small_auto.resize((w, h), Image.NEAREST)
    res4.save(os.path.join(output_dir, "auto_optimal_result.png"))

    print("All images generated in temp_image/outputs")

if __name__ == "__main__":
    process()
