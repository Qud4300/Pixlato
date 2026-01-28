import sys
import os
import json
from PIL import Image, ImageDraw

# Add project root to path
sys.path.append(os.getcwd())

from core.project_manager import ProjectManager
from core.gif_processor import process_gif

def test_project_manager():
    print("Testing ProjectManager...")
    state = {
        "source_path": "test.png",
        "pixel_size": 8,
        "max_colors": 16
    }
    
    # Save
    if ProjectManager.save_project("test_project.pcp", state):
        print(" - Save successful.")
    else:
        print(" - Save FAILED.")
        return False
        
    # Load
    loaded = ProjectManager.load_project("test_project.pcp")
    if loaded and loaded.get("pixel_size") == 8:
        print(" - Load successful.")
    else:
        print(" - Load FAILED or data mismatch.")
        return False
        
    # Cleanup
    if os.path.exists("test_project.pcp"):
        os.remove("test_project.pcp")
    return True

def test_gif_processing():
    print("Testing GIF Processing...")
    
    # Create dummy GIF
    frames = []
    for i in range(3):
        img = Image.new("RGB", (100, 100), (i*50, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rectangle([20, 20, 80, 80], fill=(0, 255, 0))
        frames.append(img)
        
    frames[0].save("test_input.gif", save_all=True, append_images=frames[1:], duration=100, loop=0)
    
    # Process
    success, count = process_gif(
        "test_input.gif", 
        "test_output.gif", 
        pixel_size=10, 
        palette_name="GameBoy", 
        custom_colors=None, 
        dither=True
    )
    
    if success and count == 3:
        print(f" - GIF processing successful. Frames: {count}")
    else:
        print(f" - GIF processing FAILED. Success: {success}, Count: {count}")
        return False
        
    # Cleanup
    if os.path.exists("test_input.gif"):
        os.remove("test_input.gif")
    if os.path.exists("test_output.gif"):
        os.remove("test_output.gif")
    return True

if __name__ == "__main__":
    p_ok = test_project_manager()
    g_ok = test_gif_processing()
    
    if p_ok and g_ok:
        print("ALL TESTS PASSED.")
        sys.exit(0)
    else:
        print("SOME TESTS FAILED.")
        sys.exit(1)
