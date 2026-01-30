import json
import os
import customtkinter as ctk
import weakref

class ThemeManager:
    def __init__(self, theme_dir="themes"):
        self.theme_dir = theme_dir
        if not os.path.exists(self.theme_dir):
            os.makedirs(self.theme_dir)
        
        # Define theme configurations with roles
        self.theme_configs = {
            "Default Dark": {
                "accent": "#3B8ED0",
                "success": "#519a73", # Soft muted green
                "text": "#FFFFFF"     # Unified white text as requested
            },
            "Midnight": {
                "accent": "#2c3e50",
                "success": "#34495e",
                "text": None # Auto contrast
            },
            "Emerald": {
                "accent": "#27ae60",
                "success": "#2ecc71",
                "text": None
            },
            "Ruby": {
                "accent": "#e74c3c",
                "success": "#c0392b",
                "text": None
            },
            "Retro Amber": {
                "accent": "#f39c12",
                "success": "#d35400",
                "text": None
            }
        }
        
        self.current_theme_name = "Default Dark"
        self._registered_widgets = [] # List of (weakref(widget), role_str)

    def register_widget(self, widget, role="accent"):
        """Registers a widget with a specific role (accent, success, etc)."""
        self._registered_widgets.append((weakref.ref(widget), role))
        self._update_single_widget(widget, role, self.current_theme_name)

    def set_theme(self, theme_name):
        """Changes the current theme and notifies all registered widgets."""
        if theme_name in self.theme_configs:
            self.current_theme_name = theme_name
            self.refresh_widgets()

    def refresh_widgets(self):
        """Updates all alive registered widgets based on their roles."""
        still_alive = []
        for ref, role in self._registered_widgets:
            widget = ref()
            if widget is not None:
                try:
                    if widget.winfo_exists():
                        self._update_single_widget(widget, role, self.current_theme_name)
                        still_alive.append((ref, role))
                except Exception:
                    pass
        self._registered_widgets = still_alive

    def _update_single_widget(self, widget, role, theme_name):
        """Applies theme logic to a specific widget based on its role and current theme."""
        config = self.theme_configs.get(theme_name, self.theme_configs["Default Dark"])
        base_color = config.get(role, config["accent"])
        
        # Determine text color: use override if present, otherwise auto-contrast
        text_color = config.get("text")
        if text_color is None:
            text_color = self.get_contrast_color(base_color)
            
        hover_color = self.adjust_brightness(base_color, -0.15)
        
        try:
            if isinstance(widget, ctk.CTkButton):
                widget.configure(fg_color=base_color, hover_color=hover_color, text_color=text_color)
            elif isinstance(widget, (ctk.CTkSlider, ctk.CTkProgressBar)):
                widget.configure(progress_color=base_color, button_color=base_color if isinstance(widget, ctk.CTkSlider) else None)
            elif isinstance(widget, (ctk.CTkSwitch, ctk.CTkCheckBox, ctk.CTkRadioButton)):
                widget.configure(fg_color=base_color, progress_color=base_color if isinstance(widget, ctk.CTkSwitch) else None)
            elif isinstance(widget, ctk.CTkOptionMenu):
                widget.configure(fg_color=base_color, button_color=base_color, button_hover_color=hover_color, text_color=text_color)
            elif isinstance(widget, ctk.CTkSegmentedButton):
                widget.configure(selected_color=base_color, selected_text_color=text_color)
        except Exception:
            pass

    def get_contrast_color(self, hex_color):
        """Determines if text should be black or white based on background luminance."""
        hex_color = hex_color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
        return "#000000" if luminance > 0.5 else "#FFFFFF"

    def adjust_brightness(self, hex_color, factor):
        """Helper to make a color darker or lighter."""
        hex_color = hex_color.lstrip('#')
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        new_rgb = [max(0, min(255, int(c * (1 + factor)))) for c in rgb]
        return '#{:02x}{:02x}{:02x}'.format(*new_rgb)

    def get_available_themes(self):
        return list(self.theme_configs.keys())

    def get_current_accent(self):
        return self.theme_configs[self.current_theme_name]["accent"]
