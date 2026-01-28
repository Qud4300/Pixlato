import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

try:
    from core.palette_parser import PaletteParser
    print("PaletteParser imported successfully.")
    
    from ui.components import CustomPaletteWindow
    print("CustomPaletteWindow imported successfully.")
    
    # Check methods
    if hasattr(CustomPaletteWindow, 'import_palette_file'):
        print("method import_palette_file exists.")
    else:
        print("method import_palette_file MISSING.")
        
    if hasattr(CustomPaletteWindow, 'extract_palette_from_image'):
        print("method extract_palette_from_image exists.")
    else:
        print("method extract_palette_from_image MISSING.")

except ImportError as e:
    print(f"ImportError: {e}")
except Exception as e:
    print(f"Error: {e}")
