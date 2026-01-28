import customtkinter as ctk
from ui.app import PixelApp
import sys
import os

# Ensure the root directory is in sys.path for imports to work correctly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def main():
    # Set global appearance
    ctk.set_appearance_mode("Dark")  # Support "Light", "Dark", "System"
    ctk.set_default_color_theme("blue")

    app = PixelApp()
    app.mainloop()

if __name__ == "__main__":
    main()
