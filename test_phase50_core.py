import os
import sys
from PIL import Image

# Add core path
sys.path.append(os.path.join(os.getcwd(), 'pixel_crafter_gui'))

from core.processor import normalize_image_geometry

def test_normalization_logic():
    print("Testing Normalization Logic...")
    
    # 1. Create source images of different sizes
    img1 = Image.new("RGBA", (100, 100), (255, 0, 0, 255)) # Red square
    img2 = Image.new("RGBA", (200, 50), (0, 255, 0, 255))  # Green wide
    
    target_size = (300, 300)
    
    # Test Upscale Strategy: Pad
    print("Scenario: Pad (Upscale 100x100 -> 300x300)")
    res1 = normalize_image_geometry(img1, target_size, strategy="Pad")
    assert res1.size == target_size
    print(f"✅ Success: Result size {res1.size}")
    
    # Test Upscale Strategy: Stretch
    print("Scenario: Stretch (Upscale 200x50 -> 300x300)")
    res2 = normalize_image_geometry(img2, target_size, strategy="Stretch")
    assert res2.size == target_size
    print(f"✅ Success: Result size {res2.size}")
    
    # Test Downscale Strategy: Center Crop
    print("Scenario: Center Crop (Downscale 300x300 -> 50x50)")
    res3 = normalize_image_geometry(res1, (50, 50), strategy="Center Crop")
    assert res3.size == (50, 50)
    print(f"✅ Success: Result size {res3.size}")

    print("\nAll Core Normalization tests PASSED.")

if __name__ == "__main__":
    test_normalization_logic()
