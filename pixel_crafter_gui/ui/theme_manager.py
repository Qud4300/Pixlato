import json
import os
import customtkinter as ctk

class ThemeManager:
    def __init__(self, theme_dir="themes"):
        self.theme_dir = theme_dir
        if not os.path.exists(self.theme_dir):
            os.makedirs(self.theme_dir)
        
        self.current_theme_name = "Default Dark"
        self.default_accent = "#3B8ED0" # Standard CTK Blue
        
    def get_available_themes(self):
        """Returns a list of available theme names based on JSON files."""
        themes = ["Default Dark", "Midnight", "Emerald", "Ruby", "Retro Amber"]
        # In future, could scan self.theme_dir for .json files
        return themes

    def apply_accent_color(self, hex_color):
        """Dynamically sets the accent color for CustomTkinter."""
        try:
            ctk.set_default_color_theme({"CTkButton": {"fg_color": hex_color, "hover_color": self._adjust_brightness(hex_color, -0.2)}})
            # Note: Full runtime theme switching in CTK is limited for some widgets
            # but we can update specific colors.
            return True
        except Exception as e:
            print(f"Error applying accent color: {e}")
            return False

    def _adjust_brightness(self, hex_color, factor):
        """Helper to make a color darker or lighter."""
        hex_color = hex_color.lstrip('#')
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        new_rgb = [max(0, min(255, int(c * (1 + factor)))) for c in rgb]
        return '#{:02x}{:02x}{:02x}'.format(*new_rgb)

    @staticmethod
    def get_preset_accent(theme_name):
        presets = {
            "Default Dark": "#3B8ED0",
            "Midnight": "#2c3e50",
            "Emerald": "#27ae60",
            "Ruby": "#e74c3c",
            "Retro Amber": "#f39c12"
        }
        return presets.get(theme_name, "#3B8ED0")
