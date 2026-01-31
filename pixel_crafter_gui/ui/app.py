import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImagePalette
from PIL.Image import DecompressionBombError
import os
import sys
import json
import threading
import time

# Import core logic
from core.processor import pixelate_image, upscale_for_preview, add_outline, remove_background
from core.palette import apply_palette_unified
from core.project_manager import ProjectManager
from core.gif_processor import process_gif
from core.image_manager import ImageManager
from ui.components import IntSpinbox, CustomPaletteWindow, ToolTip, PaletteInspector, BatchExportWindow, PluginWindow
from ui.theme_manager import ThemeManager
from ui.locale_manager import LocaleManager
from core.plugin_engine import PluginEngine

class PixelApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- Initialization ---
        current_dir = os.path.dirname(os.path.abspath(__file__))  
        project_root = os.path.dirname(current_dir)
        self.assets_dir = os.path.join(project_root, "assets")
        self.logo_path = os.path.join(self.assets_dir, "logo.png")
        self.ico_path = os.path.join(self.assets_dir, "logo.ico")

        self.locale = LocaleManager(self.assets_dir, default_lang="ko")
        self.theme_manager = ThemeManager()
        self.plugin_engine = PluginEngine(os.path.join(project_root, "plugins"))
        self.plugin_engine.discover_plugins()
        
        # Window Setup
        self.title("Pixlato - Pixel Art Studio")
        self.geometry("1400x1000")
        self.resizable(True, True)
        self.minsize(1000, 700)

        # Set App Icon
        try:
            if sys.platform.startswith("win") and os.path.exists(self.ico_path):
                self.iconbitmap(self.ico_path)
            elif os.path.exists(self.logo_path):
                icon_img = Image.open(self.logo_path)
                self.iconphoto(False, ImageTk.PhotoImage(icon_img))
        except Exception as e:
            print(f"Failed to set app icon: {e}")

        # State
        self.palette_dir = "palettes"
        if not os.path.exists(self.palette_dir): os.makedirs(self.palette_dir)
        self.last_palette_dir = self.palette_dir
        self.original_image_path = None
        self.original_size = (0, 0)
        self.raw_pixel_image = None   
        self.preview_image = None     
        self.mag_zoom = 3
        self.user_palette_colors_persistent = [(0,0,0)] * 16 
        self.active_palette_mode = "Standard" 
        self.preview_zoom = 1.0 
        self.image_manager = ImageManager()
        self.current_inventory_id = None
        self.inventory_widgets = {}
        self.presets_path = os.path.join(project_root, "palettes", "presets.json")
        self.presets = {}
        self._is_processing = False
        self._pending_reprocess = False

        self.load_default_palette()
        self.load_presets()
        
        # --- Layout Configuration ---
        self.grid_columnconfigure(0, weight=0, minsize=320)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0, minsize=180)
        self.grid_rowconfigure(1, weight=1)

        # 1. Top Navigation Bar
        self.navbar = ctk.CTkFrame(self, height=40, corner_radius=0)
        self.navbar.grid(row=0, column=0, columnspan=3, sticky="ew")
        
        self.nav_label = ctk.CTkLabel(self.navbar, text="", font=("Arial", 12, "bold"))
        self.nav_label.pack(side="left", padx=20)
        self.locale.register(self.nav_label, "nav_palette_mgmt")

        self.btn_load_pal = ctk.CTkButton(self.navbar, text="", width=80, height=28, command=self.load_palette_file)
        self.btn_load_pal.pack(side="left", padx=5)
        self.locale.register(self.btn_load_pal, "nav_load")
        self.theme_manager.register_widget(self.btn_load_pal)

        self.btn_save_pal = ctk.CTkButton(self.navbar, text="", width=120, height=28, command=self.save_palette_file)
        self.btn_save_pal.pack(side="left", padx=5)
        self.locale.register(self.btn_save_pal, "nav_save_as")
        self.theme_manager.register_widget(self.btn_save_pal)

        self.proj_label = ctk.CTkLabel(self.navbar, text="", font=("Arial", 12, "bold"))
        self.proj_label.pack(side="left", padx=(30, 10))
        self.locale.register(self.proj_label, "nav_project")

        self.btn_load_proj = ctk.CTkButton(self.navbar, text="", width=120, height=28, command=self.load_project_file)
        self.btn_load_proj.pack(side="left", padx=5)
        self.locale.register(self.btn_load_proj, "nav_open_pcp")
        self.theme_manager.register_widget(self.btn_load_proj)

        self.btn_save_proj = ctk.CTkButton(self.navbar, text="", width=100, height=28, command=self.save_project_file)
        self.btn_save_proj.pack(side="left", padx=5)
        self.locale.register(self.btn_save_proj, "nav_save_pcp")
        self.theme_manager.register_widget(self.btn_save_proj)

        self.option_lang = ctk.CTkOptionMenu(self.navbar, width=80, height=28, values=self.locale.get_available_languages(), command=self.change_language)
        self.option_lang.set(self.locale.current_lang)
        self.option_lang.pack(side="right", padx=20)
        self.theme_manager.register_widget(self.option_lang)

        # 2. Sidebar
        self.sidebar = ctk.CTkFrame(self, width=320, corner_radius=0)
        self.sidebar.grid(row=1, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        
        self.logo_label = ctk.CTkLabel(self.sidebar, text="Pixlato ✨", font=ctk.CTkFont(size=28, weight="bold"))
        self.logo_label.pack(pady=(20, 10), padx=20)

        self.label_setting_mode = ctk.CTkLabel(self.sidebar, text="", anchor="w")
        self.label_setting_mode.pack(pady=(5, 0), padx=20, fill="x")
        self.locale.register(self.label_setting_mode, "sidebar_setting_mode")

        self.setting_mode_switch = ctk.CTkSegmentedButton(self.sidebar, values=["Global", "Individual"], command=self.on_setting_mode_change)
        self.setting_mode_switch.set("Global")
        self.setting_mode_switch.pack(pady=5, padx=20, fill="x")
        self.theme_manager.register_widget(self.setting_mode_switch)

        # Fixed Bottom Sidebar Area
        self.bottom_action_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.bottom_action_frame.pack(side="bottom", fill="x", padx=10, pady=10)

        self.btn_open_mag = ctk.CTkButton(self.bottom_action_frame, text="", command=self.toggle_magnifier, fg_color="#d35400", hover_color="#e67e22")
        self.btn_open_mag.pack(pady=5, fill="x")
        self.locale.register(self.btn_open_mag, "sidebar_open_mag")
        self.mag_window = None

        self.btn_plugin_mgr = ctk.CTkButton(self.bottom_action_frame, text="", command=self.open_plugin_manager, fg_color="#16a085", hover_color="#1abc9c")
        self.btn_plugin_mgr.pack(pady=5, fill="x")
        self.locale.register(self.btn_plugin_mgr, "sidebar_plugin_mgr", prefix="🔌 ")

        self.btn_save = ctk.CTkButton(self.bottom_action_frame, text="", command=self.save_image, state="disabled", height=45, font=("Arial", 16, "bold"))
        self.btn_save.pack(pady=5, fill="x")
        self.locale.register(self.btn_save, "sidebar_export")
        self.theme_manager.register_widget(self.btn_save, role="success")

        self.status_container = ctk.CTkFrame(self.sidebar, height=30, fg_color="transparent")
        self.status_container.pack(side="bottom", pady=0, fill="x")
        self.status_container.pack_propagate(False)
        self.status_label = ctk.CTkLabel(self.status_container, text="", text_color="#2ecc71")
        self.status_label.pack(expand=True)

        # Scrollable Params Area
        self.scroll_sidebar = ctk.CTkScrollableFrame(self.sidebar, width=300, corner_radius=0, fg_color="transparent")
        self.scroll_sidebar.pack(side="top", fill="both", expand=True, padx=5, pady=5)

        self.label_mode = ctk.CTkLabel(self.scroll_sidebar, text="", anchor="w")
        self.label_mode.pack(pady=(10, 0), padx=15, fill="x")
        self.locale.register(self.label_mode, "sidebar_save_mode")

        self.mode_switch = ctk.CTkSegmentedButton(self.scroll_sidebar, values=["Style Only", "Pixelate"], command=self.on_param_change)
        self.mode_switch.set("Style Only")
        self.mode_switch.pack(pady=5, padx=15, fill="x")
        self.theme_manager.register_widget(self.mode_switch)

        self.param_frame = ctk.CTkFrame(self.scroll_sidebar, fg_color="transparent")
        self.param_frame.pack(fill="both", expand=True, padx=5)

        # Params: Pixel Size
        pixel_header = ctk.CTkFrame(self.param_frame, fg_color="transparent")
        pixel_header.pack(fill="x", pady=(10, 0))
        self.label_pixel = ctk.CTkLabel(pixel_header, text="", anchor="w", width=80)
        self.label_pixel.pack(side="left")
        self.locale.register(self.label_pixel, "sidebar_pixel_size")
        self.pixel_spin = IntSpinbox(pixel_header, from_=1, to=128, width=100, command=self.update_pixel_from_spinbox)
        self.pixel_spin.pack(side="right")
        self.pixel_spin.set(8)
        self.slider_pixel = ctk.CTkSlider(self.param_frame, from_=1, to=128, number_of_steps=127, command=self.update_pixel_from_slider)
        self.slider_pixel.set(8)
        self.slider_pixel.pack(pady=(2, 5), fill="x")
        self.theme_manager.register_widget(self.slider_pixel)

        # Params: Color Limit
        self.color_limit_group = ctk.CTkFrame(self.param_frame, fg_color="transparent")
        self.color_limit_group.pack(fill="x")
        color_header = ctk.CTkFrame(self.color_limit_group, fg_color="transparent")
        color_header.pack(fill="x", pady=(5, 0))
        self.label_color_count = ctk.CTkLabel(color_header, text="", anchor="w", width=80)
        self.label_color_count.pack(side="left")
        self.locale.register(self.label_color_count, "sidebar_color_limit")
        self.color_spinbox = IntSpinbox(color_header, from_=2, to=256, width=100, command=self.update_color_from_spinbox)
        self.color_spinbox.pack(side="right")
        self.color_spinbox.set(16)
        self.color_slider = ctk.CTkSlider(self.color_limit_group, from_=2, to=256, number_of_steps=254, command=self.update_color_from_slider)
        self.color_slider.set(16)
        self.color_slider.pack(pady=(2, 5), fill="x")
        self.theme_manager.register_widget(self.color_slider)

        # Params: Palette & FX
        self.label_pal_preset = ctk.CTkLabel(self.param_frame, text="", anchor="w")
        self.label_pal_preset.pack(pady=(5, 0), fill="x")
        self.locale.register(self.label_pal_preset, "sidebar_palette_preset")
        self.palette_values = ["Limited", "Original", "Grayscale", "GameBoy", "CGA", "Pico-8", "16-bit (4096 Colors)", "USER CUSTOM"]
        self.option_palette = ctk.CTkOptionMenu(self.param_frame, values=self.palette_values, command=self.on_palette_menu_change)
        self.option_palette.set("Limited")
        self.option_palette.pack(pady=5, fill="x")
        self.theme_manager.register_widget(self.option_palette)
        self.btn_custom_pal = ctk.CTkButton(self.param_frame, text="", command=self.open_custom_palette, fg_color="#8e44ad", hover_color="#9b59b6")
        self.btn_custom_pal.pack(pady=5, fill="x")
        self.locale.register(self.btn_custom_pal, "sidebar_edit_custom_pal")
        self.check_dither = ctk.CTkCheckBox(self.param_frame, text="", command=self.on_param_change)
        self.check_dither.select()
        self.check_dither.pack(pady=5, fill="x")
        self.locale.register(self.check_dither, "sidebar_dithering")
        self.theme_manager.register_widget(self.check_dither)

        self.label_vis_fx = ctk.CTkLabel(self.param_frame, text="", anchor="w", font=("Arial", 12, "bold"))
        self.label_vis_fx.pack(pady=(10, 0), fill="x")
        self.locale.register(self.label_vis_fx, "sidebar_visual_effects")
        self.check_remove_bg = ctk.CTkCheckBox(self.param_frame, text="", command=self.on_param_change)
        self.check_remove_bg.pack(pady=5, fill="x")
        self.locale.register(self.check_remove_bg, "sidebar_remove_bg")
        self.theme_manager.register_widget(self.check_remove_bg)
        self.check_outline = ctk.CTkCheckBox(self.param_frame, text="", command=self.on_param_change)
        self.check_outline.pack(pady=5, fill="x")
        self.locale.register(self.check_outline, "sidebar_outline")
        self.theme_manager.register_widget(self.check_outline)
        self.check_edge_enhance = ctk.CTkCheckBox(self.param_frame, text="", command=self.on_edge_enhance_toggle)
        self.check_edge_enhance.pack(pady=5, fill="x")
        self.locale.register(self.check_edge_enhance, "sidebar_edge_enhance")
        self.theme_manager.register_widget(self.check_edge_enhance)

        edge_header = ctk.CTkFrame(self.param_frame, fg_color="transparent")
        edge_header.pack(fill="x")
        self.label_edge_sens_header = ctk.CTkLabel(edge_header, text="", anchor="w")
        self.label_edge_sens_header.pack(side="left")
        self.locale.register(self.label_edge_sens_header, "sidebar_edge_sens")
        self.label_edge_sens = ctk.CTkLabel(edge_header, text="1.0", width=40, anchor="e")
        self.label_edge_sens.pack(side="right")
        self.slider_edge_sens = ctk.CTkSlider(self.param_frame, from_=0, to=10.0, number_of_steps=100, command=self.update_edge_sens_label)
        self.slider_edge_sens.set(1.0)
        self.slider_edge_sens.pack(pady=(2, 5), fill="x")
        self.theme_manager.register_widget(self.slider_edge_sens)
        self.update_edge_controls_state()

        # Downsample & Presets
        self.label_downsample = ctk.CTkLabel(self.param_frame, text="", anchor="w")
        self.label_downsample.pack(pady=(5, 0), fill="x")
        self.locale.register(self.label_downsample, "sidebar_downsample")
        self.option_downsample = ctk.CTkOptionMenu(self.param_frame, values=["Standard", "K-Means"], command=self.on_param_change)
        self.option_downsample.set("Standard")
        self.option_downsample.pack(pady=5, fill="x")
        self.theme_manager.register_widget(self.option_downsample)

        self.label_presets_header = ctk.CTkLabel(self.param_frame, text="", anchor="w", font=("Arial", 12, "bold"))
        self.label_presets_header.pack(pady=(15, 0), fill="x")
        self.locale.register(self.label_presets_header, "sidebar_presets")
        preset_frame = ctk.CTkFrame(self.param_frame, fg_color="transparent")
        preset_frame.pack(fill="x", pady=5)
        self.option_presets = ctk.CTkOptionMenu(preset_frame, values=["기본값 (Defaults)"], command=self.apply_preset)
        self.option_presets.set("기본값 (Defaults)")
        self.option_presets.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.theme_manager.register_widget(self.option_presets)
        self.btn_save_preset = ctk.CTkButton(preset_frame, text="💾", width=30, command=self.save_preset_dialog)
        self.btn_save_preset.pack(side="right")
        self.theme_manager.register_widget(self.btn_save_preset)

        # UI Theme Select
        self.label_theme_header = ctk.CTkLabel(self.param_frame, text="", anchor="w", font=("Arial", 12, "bold"))
        self.label_theme_header.pack(pady=(15, 0), fill="x")
        self.locale.register(self.label_theme_header, "sidebar_theme")
        self.option_theme = ctk.CTkOptionMenu(self.param_frame, values=self.theme_manager.get_available_themes(), command=self.change_theme)
        self.option_theme.set("Default Dark")
        self.option_theme.pack(pady=5, fill="x")
        self.theme_manager.register_widget(self.option_theme)

        # 3. Main Preview Area
        self.preview_frame = ctk.CTkFrame(self, corner_radius=12, fg_color="#1a1a1a")
        self.preview_frame.grid(row=1, column=1, padx=20, pady=20, sticky="nsew")
        self.preview_frame.grid_propagate(False)
        self.preview_frame.grid_columnconfigure(0, weight=1)
        self.preview_frame.grid_rowconfigure(0, weight=1)
        self.preview_canvas = ctk.CTkCanvas(self.preview_frame, bg="#1a1a1a", highlightthickness=0)
        self.preview_canvas.grid(row=0, column=0, sticky="nsew")
        self.palette_inspector = PaletteInspector(self.preview_frame, width=300, height=28, click_callback=self.on_palette_color_click, corner_radius=6, border_width=1, border_color="#444")
        self.palette_inspector.place(relx=0.0, rely=0.0, x=15, y=15, anchor="nw")
        
        self.palette_sort_mode = "Original"
        self.label_palette_sort = ctk.CTkLabel(self.preview_frame, text="Sort:", font=("Arial", 10), text_color="#888")
        self.label_palette_sort.place(relx=0.0, rely=0.0, x=315, y=2, anchor="nw")
        self.locale.register(self.label_palette_sort, "sort_palette")

        self.sort_menu = ctk.CTkOptionMenu(self.preview_frame, values=["Original", "Luminance", "Hue"], 
                                          width=90, height=24, font=("Arial", 10), command=self.on_palette_sort_change)
        self.sort_menu.set("Original")
        self.sort_menu.place(relx=0.0, rely=0.0, x=325, y=17, anchor="nw")
        self.theme_manager.register_widget(self.sort_menu)

        self.res_info_frame = ctk.CTkFrame(self.preview_frame, width=120, height=28, corner_radius=6, border_width=1, border_color="#444", fg_color="#2b2b2b")
        self.res_info_frame.place(relx=1.0, rely=0.0, x=-15, y=15, anchor="ne")
        self.res_info_frame.pack_propagate(False)
        self.res_label = ctk.CTkLabel(self.res_info_frame, text="0 x 0", font=("Consolas", 12, "bold"), text_color="#aaa")
        self.res_label.pack(expand=True)
        self.preview_canvas.bind("<MouseWheel>", self.on_preview_wheel)
        self.preview_canvas.bind("<Motion>", self.update_magnifier)
        self.preview_canvas.bind("<Configure>", self.on_resize)
        self.canvas_image_id = None
        self.tk_preview = None

        # 4. Right Inventory
        self.inventory_frame = ctk.CTkFrame(self, width=180, corner_radius=0)
        self.inventory_frame.grid(row=1, column=2, sticky="nsew")
        self.inventory_frame.grid_propagate(False)
        self.btn_add_to_inv = ctk.CTkButton(self.inventory_frame, text="", command=self.add_image_to_inventory, height=35)
        self.btn_add_to_inv.pack(pady=10, padx=10, fill="x")
        self.locale.register(self.btn_add_to_inv, "inv_add")
        self.theme_manager.register_widget(self.btn_add_to_inv, role="success")

        self.label_inv_header = ctk.CTkLabel(self.inventory_frame, text="", font=("Arial", 11))
        self.label_inv_header.pack(pady=(5, 0))
        self.inventory_scroll = ctk.CTkScrollableFrame(self.inventory_frame, width=160)
        self.inventory_scroll.pack(fill="both", expand=True, padx=5, pady=5)
        self.label_inv_fmt = ctk.CTkLabel(self.inventory_frame, text="", anchor="w")
        self.label_inv_fmt.pack(pady=(5, 0), padx=10, fill="x")
        self.locale.register(self.label_inv_fmt, "inv_format")
        self.format_combo = ctk.CTkOptionMenu(self.inventory_frame, values=["PNG", "JPG", "BMP", "WEBP"])
        self.format_combo.set("PNG")
        self.format_combo.pack(pady=5, padx=10, fill="x")
        self.theme_manager.register_widget(self.format_combo)
        self.btn_batch_export = ctk.CTkButton(self.inventory_frame, text="", command=self.batch_export, height=35, fg_color="#3498db")
        self.btn_batch_export.pack(pady=10, padx=10, fill="x", side="bottom")
        self.locale.register(self.btn_batch_export, "inv_save_all")

        # Initial Text Sync
        self.update_ui_text()

    # --- Methods (Correctly Indented) ---
    def load_presets(self):
        if os.path.exists(self.presets_path):
            try:
                with open(self.presets_path, "r", encoding="utf-8") as f:
                    self.presets = json.load(f)
                names = list(self.presets.keys())
                if names: self.option_presets.configure(values=names)
            except Exception as e: print(f"Error loading presets: {e}")

    def apply_preset(self, preset_name):
        if preset_name in self.presets: self.restore_ui_state(self.presets[preset_name])

    def change_theme(self, theme_name):
        self.theme_manager.set_theme(theme_name)

    def change_language(self, lang_code):
        if self.locale.load_language(lang_code): self.update_ui_text()

    def open_plugin_manager(self):
        PluginWindow(self, self.plugin_engine, on_change_callback=self.on_param_change)

    def update_ui_text(self):
        self.locale.refresh_widgets()
        self.update_inventory_count_label()

    def load_default_palette(self):
        path = os.path.join(self.palette_dir, "default_palette.json")
        if os.path.exists(path): self._load_palette_from_path(path)

    def _load_palette_from_path(self, path):
        try:
            with open(path, "r") as f:
                colors = json.load(f)
                if isinstance(colors, list) and len(colors) > 0:
                    self.user_palette_colors_persistent[:len(colors)] = [tuple(c) for c in colors]
        except Exception as e: print(f"Error loading palette: {e}")

    def save_default_palette(self):
        path = os.path.join(self.palette_dir, "default_palette.json")
        try:
            with open(path, "w") as f: json.dump(self.user_palette_colors_persistent, f)
        except Exception as e: print(f"Error saving palette: {e}")

    def load_palette_file(self):
        f = filedialog.askopenfilename(parent=self, initialdir=self.last_palette_dir, filetypes=[("JSON files", "*.json")])
        if f: 
            self.last_palette_dir = os.path.dirname(f)
            self._load_palette_from_path(f)
            self.option_palette.set("USER CUSTOM")
            self.on_palette_menu_change("USER CUSTOM")

    def save_palette_file(self):
        f = filedialog.asksaveasfilename(parent=self, initialdir=self.last_palette_dir, defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if f: 
            self.last_palette_dir = os.path.dirname(f)
            self.save_default_palette()

    def save_project_file(self):
        if not self.original_image_path: return
        state = {
            "source_path": self.original_image_path, 
            "pixel_size": int(self.slider_pixel.get()), 
            "palette_mode": self.option_palette.get(), 
            "max_colors": int(self.color_slider.get()), 
            "dither": self.check_dither.get(), 
            "outline_enabled": self.check_outline.get(), 
            "custom_colors": self.user_palette_colors_persistent, 
            "preview_zoom": self.preview_zoom
        }
        f = filedialog.asksaveasfilename(parent=self, defaultextension=".pcp", filetypes=[("Pixel Crafter Project", "*.pcp")])
        if f: ProjectManager.save_project(f, state)

    def load_project_file(self):
        f = filedialog.askopenfilename(parent=self, filetypes=[("Pixel Crafter Project", "*.pcp")])
        if not f: return
        state = ProjectManager.load_project(f)
        if state is None: messagebox.showerror("보안 오류", "파일 손상"); return
        try:
            if "source_path" in state and os.path.exists(state["source_path"]):
                self.original_image_path = state["source_path"]
                with Image.open(self.original_image_path) as img: self.original_size = img.size
                self.preview_zoom = state.get("preview_zoom", -1)
            if "pixel_size" in state: self.slider_pixel.set(state["pixel_size"])
            if "palette_mode" in state: 
                self.option_palette.set(state["palette_mode"])
                self.on_palette_menu_change(state["palette_mode"])
            if "max_colors" in state: 
                self.color_slider.set(state["max_colors"])
                self.color_spinbox.set(state["max_colors"])
            if "dither" in state: (self.check_dither.select() if state["dither"] else self.check_dither.deselect())
            if "outline_enabled" in state: (self.check_outline.select() if state["outline_enabled"] else self.check_outline.deselect())
            if "custom_colors" in state: self.user_palette_colors_persistent = [tuple(c) for c in state["custom_colors"]]
            self.process_image()
            self.btn_save.configure(state="normal")
        except Exception as e: print(f"Error project load: {e}")

    def on_palette_menu_change(self, value):
        if value in ["Original", "GameBoy", "CGA", "Pico-8", "USER CUSTOM", "16-bit (4096 Colors)"]: self.color_limit_group.pack_forget()
        else: self.color_limit_group.pack(after=self.slider_pixel, fill="x")
        self.active_palette_mode = "Custom_User" if value == "USER CUSTOM" else ("Custom_16bit" if value == "16-bit (4096 Colors)" else "Standard")
        self.on_param_change()

    def on_palette_color_click(self, index, color): self.open_custom_palette(initial_index=index)

    def open_custom_palette(self, initial_index=0):
        current = self.palette_inspector.colors if self.palette_inspector.colors else self.user_palette_colors_persistent
        CustomPaletteWindow(self, self.on_custom_palette_applied, initial_colors=current, initial_index=initial_index, live_callback=self.on_live_palette_update)

    def on_live_palette_update(self, colors):
        if colors: 
            self.user_palette_colors_persistent[:len(colors)] = colors
            self.active_palette_mode = "Custom_User"
            self.on_param_change()

    def on_custom_palette_applied(self, mode, colors):
        if colors: 
            self.user_palette_colors_persistent[:len(colors)] = colors
            self.save_default_palette()
        self.active_palette_mode = "Custom_User"
        self.option_palette.set("USER CUSTOM")
        self.on_palette_menu_change("USER CUSTOM")

    def update_pixel_from_slider(self, value): self.pixel_spin.set(int(value)); self.on_param_change()
    def update_pixel_from_spinbox(self): 
        v = self.pixel_spin.get()
        if v is not None: self.slider_pixel.set(v); self.on_param_change()

    def update_color_from_slider(self, value): self.color_spinbox.set(int(value)); self.on_param_change()
    def update_color_from_spinbox(self):
        v = self.color_spinbox.get()
        if v is not None: 
            v = max(2, min(256, v))
            self.color_spinbox.set(v)
            self.color_slider.set(v)
            self.on_param_change()

    def update_edge_sens_label(self, value): self.label_edge_sens.configure(text=f"{float(value):.1f}"); self.on_param_change()
    def on_edge_enhance_toggle(self): self.update_edge_controls_state(); self.on_param_change()
    def update_edge_controls_state(self):
        if self.check_edge_enhance.get(): 
            self.slider_edge_sens.configure(state="normal", progress_color=self.theme_manager.get_current_accent())
            self.label_edge_sens.configure(text_color="#FFFFFF")
        else: 
            self.slider_edge_sens.configure(state="disabled", progress_color="gray")
            self.label_edge_sens.configure(text_color="gray")

    def on_setting_mode_change(self, value):
        if value == "Individual" and self.current_inventory_id is not None:
            e = self.image_manager.get_image(self.current_inventory_id)
            if e and e["params"] is None: e["params"] = self.capture_ui_state()

    def capture_ui_state(self):
        return {
            "save_mode": self.mode_switch.get(), 
            "pixel_size": int(self.slider_pixel.get()), 
            "color_count": int(self.color_slider.get()), 
            "palette_mode": self.option_palette.get(), 
            "dither": self.check_dither.get(), 
            "remove_bg": self.check_remove_bg.get(), 
            "outline": self.check_outline.get(), 
            "edge_enhance": self.check_edge_enhance.get(), 
            "edge_sensitivity": float(self.slider_edge_sens.get()), 
            "downsample_method": self.option_downsample.get(), 
            "custom_colors": list(self.user_palette_colors_persistent)
        }

    def restore_ui_state(self, params):
        if not params: return
        try:
            if "save_mode" in params: self.mode_switch.set(params["save_mode"])
            if "pixel_size" in params: 
                self.slider_pixel.set(params["pixel_size"])
                self.pixel_spin.set(params["pixel_size"])
            if "color_count" in params: 
                self.color_slider.set(params["color_count"])
                self.color_spinbox.set(params["color_count"])
            if "palette_mode" in params: 
                self.option_palette.set(params["palette_mode"])
                self.on_palette_menu_change(params["palette_mode"])
            if "dither" in params: (self.check_dither.select() if params["dither"] else self.check_dither.deselect())
            if "remove_bg" in params: (self.check_remove_bg.select() if params["remove_bg"] else self.check_remove_bg.deselect())
            if "outline" in params: (self.check_outline.select() if params["outline"] else self.check_outline.deselect())
            if "edge_enhance" in params: 
                (self.check_edge_enhance.select() if params["edge_enhance"] else self.check_edge_enhance.deselect())
                self.update_edge_controls_state()
            if "edge_sensitivity" in params: 
                self.slider_edge_sens.set(params["edge_sensitivity"])
                self.label_edge_sens.configure(text=f"{params['edge_sensitivity']:.1f}")
            if "downsample_method" in params: self.option_downsample.set(params["downsample_method"])
            if "custom_colors" in params: self.user_palette_colors_persistent = [tuple(c) for c in params["custom_colors"]]
            self.on_param_change()
        except Exception as e: print(f"Error restore: {e}")

    def on_param_change(self, *args):
        if self.current_inventory_id is not None:
            if self.setting_mode_switch.get() == "Individual":
                e = self.image_manager.get_image(self.current_inventory_id)
                if e: e["params"] = self.capture_ui_state()
            e = self.image_manager.get_image(self.current_inventory_id)
            if e: self.process_inventory_image(e["pil_image"])
        elif self.original_image_path: 
            self.process_image()

    def select_inventory_image(self, image_id):
        self.current_inventory_id = image_id
        e = self.image_manager.get_image(image_id)
        if e:
            if self.setting_mode_switch.get() == "Individual":
                if e["params"]: self.restore_ui_state(e["params"])
                else: 
                    e["params"] = self.capture_ui_state()
                    self.process_inventory_image(e["pil_image"])
            else: 
                self.process_inventory_image(e["pil_image"])

    def process_inventory_image(self, pil_image): 
        self._start_threaded_process("pil", pil_image)

    def open_image(self):
        f = filedialog.askopenfilename(parent=self, filetypes=[("Image", "*.png *.jpg *.jpeg *.webp *.gif *.bmp")])
        if f:
            try:
                self.original_image_path = f
                with Image.open(f) as img: self.original_size = img.size
                self.preview_zoom = -1
                self.process_image()
                self.btn_save.configure(state="normal")
            except Exception as e: messagebox.showerror("오류", f"이미지 로드 실패: {e}")

    def process_image(self):
        if self.original_image_path: 
            self._start_threaded_process("path", self.original_image_path)

    def _start_threaded_process(self, source_type, source_data):
        if self._is_processing: 
            self._pending_reprocess = True
            self._pending_source = (source_type, source_data)
            return
        self._is_processing = True
        self.status_label.configure(text=self.locale.get("status_processing"))
        self.btn_save.configure(state="disabled")
        params = self.capture_ui_state()
        params["user_pal"] = self.user_palette_colors_persistent
        params["palette_choice"] = params["palette_mode"]

        def run():
            try:
                if source_type == "path":
                    with Image.open(source_data) as tmp: self.original_size = tmp.size
                    raw = pixelate_image(source_data, params["pixel_size"], edge_enhance=params["edge_enhance"], edge_sensitivity=params["edge_sensitivity"], downsample_method=params["downsample_method"], remove_bg=params["remove_bg"], plugin_engine=self.plugin_engine, plugin_params=params)
                else:
                    img = source_data.convert("RGBA")
                    self.original_size = img.size
                    img = self.plugin_engine.execute_hook("PRE_PROCESS", img, params)
                    if params["remove_bg"]: img = remove_background(img, tolerance=40)
                    if params["edge_enhance"]: 
                        from core.processor import enhance_internal_edges
                        img = enhance_internal_edges(img, params["edge_sensitivity"])
                    img = self.plugin_engine.execute_hook("PRE_DOWNSAMPLE", img, params)
                    sw, sh = max(1, img.size[0] // params["pixel_size"]), max(1, img.size[1] // params["pixel_size"])
                    if params["downsample_method"] == "K-Means":
                        from core.processor import downsample_kmeans_adaptive
                        raw = downsample_kmeans_adaptive(img, params["pixel_size"], sw, sh)
                    else: 
                        raw = img.resize((sw, sh), resample=Image.BOX)
                    raw = self.plugin_engine.execute_hook("POST_DOWNSAMPLE", raw, params)

                if not raw: 
                    self.after(0, self._on_processing_complete, None)
                    return
                
                p_name, p_param = ("Custom_User", params["user_pal"]) if params["palette_choice"] == "USER CUSTOM" else (("Custom_16bit", None) if params["palette_choice"] == "16-bit (4096 Colors)" else (params["palette_choice"], params["color_count"]))
                proc = apply_palette_unified(raw, p_name, custom_colors=p_param, dither=params["dither"])
                proc = self.plugin_engine.execute_hook("POST_PALETTE", proc, params)
                if params["outline"]: proc = add_outline(proc)
                proc = self.plugin_engine.execute_hook("FINAL_IMAGE", proc, params)
                prev = upscale_for_preview(proc, self.original_size)
                self.after(0, self._on_processing_complete, proc, prev)
            except Exception as e: 
                print(f"Thread error: {e}")
                self.after(0, self._on_processing_complete, None)

        threading.Thread(target=run, daemon=True).start()

    def _on_processing_complete(self, proc, prev=None):
        self._is_processing = False
        self.status_label.configure(text="")
        if proc:
            self.raw_pixel_image, self.preview_image = proc, prev
            self.display_image()
            self.btn_save.configure(state="normal")
            try:
                clrs = self.extract_used_colors(proc)
                self.palette_inspector.update_colors(clrs)
                rw, rh = proc.size if self.mode_switch.get() == "Pixelate" else self.original_size
                self.res_label.configure(text=f"{rw} x {rh}")
            except: pass
        if self._pending_reprocess: 
            self._pending_reprocess = False
            self._start_threaded_process(*self._pending_source)

    def on_palette_sort_change(self, mode):
        self.palette_sort_mode = mode
        if hasattr(self, "raw_pixel_image") and self.raw_pixel_image:
            clrs = self.extract_used_colors(self.raw_pixel_image)
            self.palette_inspector.update_colors(clrs)

    def extract_used_colors(self, pil_img):
        from core.palette import sort_colors
        tmp = pil_img.convert("RGB")
        colors = tmp.getcolors(maxcolors=4096)
        if not colors: return []
        # Extract RGB tuples from (count, color) list
        raw_colors = [c[1] for c in colors]
        # Sort by frequency first to get top 16, then apply user sorting
        freq_sorted = sorted(colors, key=lambda x: x[0], reverse=True)
        top_16 = [c[1] for c in freq_sorted[:16]]
        return sort_colors(top_16, self.palette_sort_mode)

    def display_image(self):
        if not self.preview_image: return
        params = self.capture_ui_state()
        
        # UI_PRE_RENDER Hook: Modification of the full-res preview image
        render_img = self.plugin_engine.execute_hook("UI_PRE_RENDER", self.preview_image, params)
        
        cw, ch = self.preview_canvas.winfo_width(), self.preview_canvas.winfo_height()
        if cw <= 1: cw, ch = 800, 600
        iw, ih = render_img.size
        if self.preview_zoom == -1: self.preview_zoom = min(cw / iw, ch / ih) * 0.9
        nw, nh = int(iw * self.preview_zoom), int(ih * self.preview_zoom)
        
        disp = render_img.resize((nw, nh), Image.NEAREST)
        
        # UI_POST_RENDER Hook: Modification of the zoomed display image (e.g., UI overlays)
        disp = self.plugin_engine.execute_hook("UI_POST_RENDER", disp, params)
        
        self.tk_preview = ImageTk.PhotoImage(disp)
        if self.canvas_image_id: self.preview_canvas.delete(self.canvas_image_id)
        self.canvas_image_id = self.preview_canvas.create_image(cw//2, ch//2, image=self.tk_preview, anchor="center")

    def on_preview_wheel(self, event):
        if not self.preview_image: return
        self.preview_zoom = max(0.1, min(20.0, self.preview_zoom * (1.1 if event.delta > 0 else 0.9)))
        self.display_image()

    def on_resize(self, event): 
        if self.preview_image: self.display_image()

    def toggle_magnifier(self):
        if self.mag_window is None or not self.mag_window.winfo_exists(): 
            self.mag_window = MagnifierWindow(self)
        else: 
            self.mag_window.focus()

    def update_magnifier(self, event):
        if not self.preview_image or not self.canvas_image_id or not (self.mag_window and self.mag_window.winfo_exists()): return
        cw, ch = self.preview_canvas.winfo_width(), self.preview_canvas.winfo_height()
        iw, ih = self.preview_image.size
        nw, nh = int(iw * self.preview_zoom), int(ih * self.preview_zoom)
        sx = int((event.x - (cw//2 - nw//2)) / self.preview_zoom)
        sy = int((event.y - (ch//2 - nh//2)) / self.preview_zoom)
        if 0 <= sx < iw and 0 <= sy < ih: 
            self.mag_window.update_zoom(self.preview_image, (sx, sy), self.mag_zoom)

    def save_image(self):
        p = self.original_image_path
        if self.current_inventory_id is not None:
            e = self.image_manager.get_image(self.current_inventory_id)
            if e: p = e["path"]
        if not p: return
        is_gif = p.lower().endswith('.gif')
        types = ([("GIF Animation", "*.gif")] if is_gif else []) + [("PNG", "*.png")]
        f = filedialog.asksaveasfilename(parent=self, defaultextension=(".gif" if is_gif else ".png"), filetypes=types)
        if f:
            f = os.path.normpath(f)
            if is_gif and f.lower().endswith('.gif'):
                self.btn_save.configure(text="GIF...", state="disabled")
                self.update()
                ch = self.option_palette.get()
                pn, pp = ("Custom_User", self.user_palette_colors_persistent) if ch == "USER CUSTOM" else (("Custom_16bit", None) if ch == "16-bit (4096 Colors)" else (ch, int(self.color_slider.get())))
                process_gif(p, f, int(self.slider_pixel.get()), pn, pp, self.check_dither.get(), self.check_outline.get())
                self.btn_save.configure(text=self.locale.get("sidebar_export"), state="normal")
            else:
                final = self.raw_pixel_image if self.mode_switch.get() == "Pixelate" else self.preview_image
                if f.lower().endswith(('.jpg', '.bmp')): final = final.convert("RGB")
                final.save(f)

    def add_image_to_inventory(self):
        paths = filedialog.askopenfilenames(parent=self, filetypes=[("Image", "*.png *.jpg *.jpeg *.webp *.gif *.bmp")])
        new_ids = []
        for pt in paths: new_ids.extend(self.image_manager.add_image(pt))
        for i in new_ids:
            e = self.image_manager.get_image(i)
            if e: self._create_inventory_item(e)
        self.update_inventory_count_label()
        if self.image_manager.count() > 0 and self.current_inventory_id is None: 
            self.select_inventory_image(self.image_manager.get_all()[0]["id"])

    def update_inventory_count_label(self):
        for w in self.inventory_frame.winfo_children():
            if isinstance(w, ctk.CTkLabel) and (self.locale.get("inv_title") in w.cget("text") or "인벤토리" in w.cget("text")):
                w.configure(text=f"{self.locale.get('inv_title')} ({self.image_manager.count()}/256)")
                break

    def _create_inventory_item(self, e):
        fid = e["id"]
        item = ctk.CTkFrame(self.inventory_scroll, height=70, fg_color="#2a2a2a", corner_radius=8)
        item.pack(fill="x", pady=3, padx=2)
        item.pack_propagate(False)
        self.inventory_widgets[fid] = item
        thumb = e["thumbnail"]
        ctk_t = ctk.CTkImage(light_image=thumb, dark_image=thumb, size=(50, 50))
        tl = ctk.CTkLabel(item, image=ctk_t, text="")
        tl.pack(side="left", padx=5, pady=5)
        tl.image = ctk_t
        nl = ctk.CTkLabel(item, text=e["name"][:12], font=("Arial", 10), anchor="w")
        nl.pack(side="left", fill="x", expand=True, padx=5)
        db = ctk.CTkButton(item, text="X", width=20, height=20, fg_color="#e74c3c", command=lambda: self.remove_from_inventory(fid))
        db.place(relx=1.0, rely=0, anchor="ne", x=-5, y=5)
        db.lower()
        item.bind("<Enter>", lambda e: db.lift())
        item.bind("<Leave>", lambda e: db.lower())
        item.bind("<Button-1>", lambda e: self.select_inventory_image(fid))
        tl.bind("<Button-1>", lambda e: self.select_inventory_image(fid))
        nl.bind("<Button-1>", lambda e: self.select_inventory_image(fid))

    def remove_from_inventory(self, iid):
        if iid in self.inventory_widgets: 
            self.inventory_widgets[iid].destroy()
            del self.inventory_widgets[iid]
        self.image_manager.remove_image(iid)
        self.update_inventory_count_label()
        if self.current_inventory_id == iid: 
            self.current_inventory_id = None
            if self.image_manager.count() > 0:
                self.select_inventory_image(self.image_manager.get_all()[0]["id"])

    def batch_export(self):
        if self.image_manager.count() > 0: 
            BatchExportWindow(self, self._start_batch_export_process)

    def _start_batch_export_process(self, od, fs, win):
        import concurrent.futures
        from collections import defaultdict
        g, mode, entries = self.capture_ui_state(), self.setting_mode_switch.get(), self.image_manager.get_all()
        
        # Group by original path to handle GIFs
        groups = defaultdict(list)
        for e in entries:
            groups[e["path"]].append(e)

        def process_frame(e, target_params):
            p = target_params
            img = e["pil_image"].convert("RGBA")
            if p.get("remove_bg"): img = remove_background(img)
            if p.get("edge_enhance"): 
                from core.processor import enhance_internal_edges
                img = enhance_internal_edges(img, p["edge_sensitivity"])
            sw, sh = max(1, img.size[0] // p["pixel_size"]), max(1, img.size[1] // p["pixel_size"])
            small = img.resize((sw, sh), resample=Image.BOX)
            pn, pp = ("Custom_User", p["custom_colors"]) if p["palette_mode"] == "USER CUSTOM" else (("Custom_16bit", None) if p["palette_mode"] == "16-bit (4096 Colors)" else (p["palette_mode"], p.get("color_count", 16)))
            proc = apply_palette_unified(small, pn, pp, p.get("dither", True))
            if p.get("outline"): proc = add_outline(proc)
            return proc.resize(e["pil_image"].size, Image.NEAREST)

        def task_individual(e, f):
            try:
                p = e["params"] if mode == "Individual" and e["params"] else g
                final = process_frame(e, p)
                if f.lower() in ["jpg", "bmp"]: final = final.convert("RGB")
                save_name = f"{os.path.basename(e['name'])}_pixel.{f.lower()}"
                final.save(os.path.join(od, save_name))
                return True, f"✅ {e['name']} ({f})"
            except Exception as ex: return False, f"❌ {e['name']} ({f}): {ex}"

        def task_gif_group(path, frames):
            try:
                processed_frames = []
                for e in frames:
                    p = e["params"] if mode == "Individual" and e["params"] else g
                    processed_frames.append(process_frame(e, p).convert("P", palette=Image.ADAPTIVE))
                
                base_name = os.path.splitext(os.path.basename(path))[0]
                save_path = os.path.join(od, f"{base_name}_pixel.gif")
                
                # Attempt to get original duration
                dur = 100
                try:
                    with Image.open(path) as orig:
                        dur = orig.info.get('duration', 100)
                except: pass

                if processed_frames:
                    processed_frames[0].save(
                        save_path,
                        save_all=True,
                        append_images=processed_frames[1:],
                        duration=dur,
                        loop=0,
                        optimize=False
                    )
                return True, f"✅ GIF: {base_name}"
            except Exception as ex: return False, f"❌ GIF: {ex}"

        def run():
            done = 0
            tasks = []
            for f in fs:
                if f == "GIF":
                    for path, frames in groups.items():
                        tasks.append(("gif", path, frames))
                else:
                    for e in entries:
                        tasks.append(("individual", e, f))

            total = len(tasks)
            if total == 0:
                self.after(0, lambda: win.btn_start.configure(state="normal", text="작업 완료"))
                return

            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
                fut = []
                for t in tasks:
                    if t[0] == "gif":
                        fut.append(ex.submit(task_gif_group, t[1], t[2]))
                    else:
                        fut.append(ex.submit(task_individual, t[1], t[2]))
                
                for f in concurrent.futures.as_completed(fut):
                    done += 1
                    s, m = f.result()
                    self.after(0, lambda m=m: win.log(m))
                    self.after(0, lambda d=done, tl=total: win.update_progress(d, tl))
            self.after(0, lambda: win.btn_start.configure(state="normal", text="작업 완료"))
        
        threading.Thread(target=run, daemon=True).start()

    def save_preset_dialog(self):
        dialog = ctk.CTkInputDialog(text="새로운 프리셋 이름을 입력하세요:", title="프리셋 저장")
        name = dialog.get_input()
        if name:
            self.presets[name] = self.capture_ui_state()
            try:
                with open(self.presets_path, "w", encoding="utf-8") as f: 
                    json.dump(self.presets, f, indent=4)
                self.option_presets.configure(values=list(self.presets.keys()))
                self.option_presets.set(name)
            except Exception as e: print(f"Error saving preset: {e}")

class MagnifierWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("🔍 Pixel Magnifier")
        self.geometry("300x380")
        self.attributes("-topmost", True)
        self.parent = parent
        self.display_label = ctk.CTkLabel(self, text="", width=280, height=280, fg_color="black", corner_radius=10)
        self.display_label.pack(pady=10, padx=10)
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.pack(pady=5, fill="x", padx=10)
        ctk.CTkButton(f, text="-", width=40, command=self.zoom_out).pack(side="left", padx=5)
        self.label_zoom = ctk.CTkLabel(f, text=f"{self.parent.mag_zoom}x", font=("Arial", 16, "bold"))
        self.label_zoom.pack(side="left", expand=True)
        ctk.CTkButton(f, text="+", width=40, command=self.zoom_in).pack(side="left", padx=5)
    
    def zoom_in(self):
        if self.parent.mag_zoom < 16: 
            self.parent.mag_zoom += 1
            self.label_zoom.configure(text=f"{self.parent.mag_zoom}x")
    
    def zoom_out(self):
        if self.parent.mag_zoom > 2: 
            self.parent.mag_zoom -= 1
            self.label_zoom.configure(text=f"{self.parent.mag_zoom}x")
    
    def update_zoom(self, img, pos, z):
        sz = max(1, int(280 / z))
        sx, sy = pos
        l, t = max(0, sx - sz // 2), max(0, sy - sz // 2)
        r, b = min(img.size[0], l + sz), min(img.size[1], t + sz)
        crop = img.crop((l, t, r, b)).resize((280, 280), Image.NEAREST)
        ci = ctk.CTkImage(light_image=crop, dark_image=crop, size=(280, 280))
        self.display_label.configure(image=ci, text="")
        self.display_label.image = ci

if __name__ == "__main__": 
    app = PixelApp()
    app.mainloop()