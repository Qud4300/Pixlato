
import os
import sys
from PIL import Image

# Add core path
sys.path.append(os.path.join(os.getcwd(), 'pixel_crafter_gui'))

from core.palette import apply_palette_unified

def test_formats():
    source_path = r'temp_image\pixlato_logic_overlap_logo_v2.png'
    output_dir = r'temp_image\outputs'
    
    if not os.path.exists(source_path):
        print(f"Source not found: {source_path}")
        return

    img = Image.open(source_path).convert("RGBA")
    
    # Test TGA saving logic (with alpha handling emulation)
    print("Testing TGA save...")
    final = img.copy()
    if final.mode == "RGBA":
        bg = Image.new("RGB", final.size, (0, 0, 0))
        bg.paste(final, mask=final.split()[3])
        final = bg
    final.save(os.path.join(output_dir, "test_save.tga"))
    print("✅ TGA saved.")

    # Test TIFF saving logic
    print("Testing TIFF save...")
    img.save(os.path.join(output_dir, "test_save.tiff"))
    print("✅ TIFF saved.")

    print("Verification complete.")

if __name__ == "__main__":
    test_formats()
