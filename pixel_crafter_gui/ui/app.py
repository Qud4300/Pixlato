import customtkinter as ctk
from tkinter import filedialog
from PIL import Image, ImageTk
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
from ui.components import IntSpinbox, CustomPaletteWindow, ToolTip, PaletteInspector

class PixelApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Window Setup
        self.title("Pixlato - Pixel Art Studio")
        self.geometry("1400x1000")
        self.resizable(True, True)
        
        # Minimum size to ensure layout doesn't collapse
        self.minsize(1000, 700)

        # Asset Paths
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        self.assets_dir = os.path.join(project_root, "assets")
        self.logo_path = os.path.join(self.assets_dir, "logo.png")
        self.ico_path = os.path.join(self.assets_dir, "logo.ico")

        # Set App Icon
        try:
            if sys.platform.startswith("win") and os.path.exists(self.ico_path):
                self.iconbitmap(self.ico_path)
            elif os.path.exists(self.logo_path):
                icon_img = Image.open(self.logo_path)
                self.iconphoto(False, ImageTk.PhotoImage(icon_img))
        except Exception as e:
            print(f"Failed to set app icon: {e}")

        # Ensure directory exists
        self.palette_dir = "palettes"
        if not os.path.exists(self.palette_dir):
            os.makedirs(self.palette_dir)
        self.last_palette_dir = self.palette_dir

        # State
        self.original_image_path = None
        self.original_size = (0, 0)
        self.raw_pixel_image = None   
        self.preview_image = None     
        self.mag_zoom = 3
        
        # State for Custom Palettes
        self.user_palette_colors_persistent = [(0,0,0)] * 16 
        self.active_palette_mode = "Standard" 
        
        # Load Existing Palette if available
        self.load_default_palette()
        
        # State for Preview Zoom
        self.preview_zoom = 1.0 
        
        # Image Manager for batch processing
        self.image_manager = ImageManager()
        self.current_inventory_id = None  # Currently selected image in inventory
        self.inventory_widgets = {}  # image_id -> item_frame
        
        # Load Presets
        self.presets_path = os.path.join(project_root, "palettes", "presets.json")
        self.presets = {}
        self.load_presets()
        
        # Threading & Processing State
        self._is_processing = False
        self._pending_reprocess = False
        self._last_processed_source = None # Stores whether we are processing original or inventory
        
        # Layout Config (3 columns: sidebar, preview, inventory)
        self.grid_columnconfigure(0, weight=0, minsize=320)  # Fixed sidebar width
        self.grid_columnconfigure(1, weight=1)  # Preview (expandable)
        self.grid_columnconfigure(2, weight=0, minsize=180)  # Fixed inventory width
        self.grid_rowconfigure(1, weight=1) # Row 0 is Navbar, Row 1 is Content

        # --- Top Navigation Bar ---
        self.navbar = ctk.CTkFrame(self, height=40, corner_radius=0)
        self.navbar.grid(row=0, column=0, columnspan=3, sticky="ew")
        
        self.nav_label = ctk.CTkLabel(self.navbar, text="📁 팔레트 관리:", font=("Arial", 12, "bold"))
        self.nav_label.pack(side="left", padx=20)
        
        self.btn_load_pal = ctk.CTkButton(self.navbar, text="불러오기 (Load)", width=100, height=28, fg_color="#34495e", command=self.load_palette_file)
        self.btn_load_pal.pack(side="left", padx=5)
        
        self.btn_save_pal = ctk.CTkButton(self.navbar, text="다른 이름으로 저장 (Save As)", width=160, height=28, fg_color="#34495e", command=self.save_palette_file)
        self.btn_save_pal.pack(side="left", padx=5)

        # --- Project Management ---
        self.proj_label = ctk.CTkLabel(self.navbar, text="💾 프로젝트:", font=("Arial", 12, "bold"))
        self.proj_label.pack(side="left", padx=(30, 10))

        self.btn_load_proj = ctk.CTkButton(self.navbar, text="불러오기 (Open .pcp)", width=140, height=28, fg_color="#2c3e50", command=self.load_project_file)
        self.btn_load_proj.pack(side="left", padx=5)

        self.btn_save_proj = ctk.CTkButton(self.navbar, text="저장 (Save .pcp)", width=120, height=28, fg_color="#2c3e50", command=self.save_project_file)
        self.btn_save_proj.pack(side="left", padx=5)

        # --- Sidebar ---
        self.sidebar = ctk.CTkFrame(self, width=320, corner_radius=0)
        self.sidebar.grid(row=1, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False) # CRITICAL: Prevent content from resizing sidebar
        
        # Logo Integration
        if os.path.exists(self.logo_path):
            try:
                pil_logo = Image.open(self.logo_path)
                # Resize keeping aspect ratio, max width 250
                base_width = 250
                w_percent = (base_width / float(pil_logo.size[0]))
                h_size = int((float(pil_logo.size[1]) * float(w_percent)))
                
                logo_ctk = ctk.CTkImage(light_image=pil_logo, dark_image=pil_logo, size=(base_width, h_size))
                self.logo_label = ctk.CTkLabel(self.sidebar, text="", image=logo_ctk)
            except Exception as e:
                 print(f"Error loading logo: {e}")
                 self.logo_label = ctk.CTkLabel(self.sidebar, text="Pixlato ✨", font=ctk.CTkFont(size=28, weight="bold"))
        else:
            self.logo_label = ctk.CTkLabel(self.sidebar, text="Pixlato ✨", font=ctk.CTkFont(size=28, weight="bold"))
            
        self.logo_label.pack(pady=20, padx=20)

        # Setting Mode Selection (Phase 19)
        self.label_setting_mode = ctk.CTkLabel(self.sidebar, text="설정 모드 (Setting Mode):", anchor="w")
        self.label_setting_mode.pack(pady=(10, 0), padx=20, fill="x")
        self.setting_mode_switch = ctk.CTkSegmentedButton(self.sidebar, values=["Global", "Individual"], command=self.on_setting_mode_change)
        self.setting_mode_switch.set("Global")
        self.setting_mode_switch.pack(pady=5, padx=20, fill="x")
        ToolTip(self.label_setting_mode, text="Global: 하나의 설정을 모든 이미지에 동일하게 적용합니다.\nIndividual: 각 이미지마다 개별적인 설정값을 저장하고 복구합니다.")

        # Mode Selection
        self.label_mode = ctk.CTkLabel(self.sidebar, text="저장 모드 (Save Mode):", anchor="w")
        self.label_mode.pack(pady=(10, 0), padx=20, fill="x")
        self.mode_switch = ctk.CTkSegmentedButton(self.sidebar, values=["Style Only", "Pixelate"], command=self.on_param_change)
        self.mode_switch.set("Style Only")
        self.mode_switch.pack(pady=5, padx=20, fill="x")
        
        # Tooltips for Save Mode
        ToolTip(self.label_mode, text="Style Only: 이미지 해상도는 유지하되 픽셀 아트 스타일만 적용합니다.\nPixelate: 실제 이미지 해상도를 줄여 픽셀화합니다.")

        # Params Container
        self.param_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.param_frame.pack(fill="both", expand=True, padx=10)

        # Pixel Size Section (Compact)
        pixel_header = ctk.CTkFrame(self.param_frame, fg_color="transparent")
        pixel_header.pack(fill="x", pady=(10, 0))
        self.label_pixel = ctk.CTkLabel(pixel_header, text="Pixel Size:", anchor="w", width=80)
        self.label_pixel.pack(side="left")
        self.pixel_spin = IntSpinbox(pixel_header, from_=1, to=128, width=100, command=self.update_pixel_from_spinbox)
        self.pixel_spin.pack(side="right")
        self.pixel_spin.set(8)
        
        self.slider_pixel = ctk.CTkSlider(self.param_frame, from_=1, to=128, number_of_steps=127, command=self.update_pixel_from_slider)
        self.slider_pixel.set(8)
        self.slider_pixel.pack(pady=(2, 5), fill="x")

        # Color Count Section (Compact)
        self.color_limit_group = ctk.CTkFrame(self.param_frame, fg_color="transparent")
        self.color_limit_group.pack(fill="x")
        
        color_header = ctk.CTkFrame(self.color_limit_group, fg_color="transparent")
        color_header.pack(fill="x", pady=(5, 0))
        self.label_color_count = ctk.CTkLabel(color_header, text="색상 제한:", anchor="w", width=80)
        self.label_color_count.pack(side="left")
        self.color_spinbox = IntSpinbox(color_header, from_=2, to=256, width=100, command=self.update_color_from_spinbox)
        self.color_spinbox.pack(side="right")
        self.color_spinbox.set(16)
        
        self.color_slider = ctk.CTkSlider(self.color_limit_group, from_=2, to=256, number_of_steps=254, command=self.update_color_from_slider)
        self.color_slider.set(16)
        self.color_slider.pack(pady=(2, 5), fill="x")

        # Palette Section
        ctk.CTkLabel(self.param_frame, text="팔레트 프리셋:", anchor="w").pack(pady=(5, 0), fill="x")
        self.palette_values = ["Limited", "Original", "Grayscale", "GameBoy", "CGA", "Pico-8", "16-bit (4096 Colors)", "USER CUSTOM"]
        self.option_palette = ctk.CTkOptionMenu(self.param_frame, values=self.palette_values, command=self.on_palette_menu_change)
        self.option_palette.set("Limited")
        self.option_palette.pack(pady=5, fill="x")

        self.btn_custom_pal = ctk.CTkButton(self.param_frame, text="🎨 커스텀 팔레트 편집", command=self.open_custom_palette, fg_color="#8e44ad", hover_color="#9b59b6")
        self.btn_custom_pal.pack(pady=5, fill="x")

        self.check_dither = ctk.CTkCheckBox(self.param_frame, text="디더링 (Dithering)", command=self.on_param_change)
        self.check_dither.select()
        self.check_dither.pack(pady=5, fill="x")

        # Visual Effects Section
        ctk.CTkLabel(self.param_frame, text="비주얼 효과:", anchor="w", font=("Arial", 12, "bold")).pack(pady=(10, 0), fill="x")
        
        self.check_remove_bg = ctk.CTkCheckBox(self.param_frame, text="배경 제거 (Remove BG)", command=self.on_param_change)
        self.check_remove_bg.pack(pady=5, fill="x")
        ToolTip(self.check_remove_bg, text="이미지의 모서리 색상을 감지하여 배경을 투명하게 만듭니다.")

        self.check_outline = ctk.CTkCheckBox(self.param_frame, text="외곽선 추가 (Outline)", command=self.on_param_change)
        self.check_outline.pack(pady=5, fill="x")

        self.check_edge_enhance = ctk.CTkCheckBox(self.param_frame, text="내부 엣지 강조 (Edge)", command=self.on_edge_enhance_toggle)
        self.check_edge_enhance.pack(pady=5, fill="x")
        
        edge_header = ctk.CTkFrame(self.param_frame, fg_color="transparent")
        edge_header.pack(fill="x")
        ctk.CTkLabel(edge_header, text="엣지 강도:", anchor="w").pack(side="left")
        self.label_edge_sens = ctk.CTkLabel(edge_header, text="1.0", width=40, anchor="e")
        self.label_edge_sens.pack(side="right")
        
        self.slider_edge_sens = ctk.CTkSlider(self.param_frame, from_=0, to=10.0, number_of_steps=100, command=self.update_edge_sens_label)
        self.slider_edge_sens.set(1.0)
        self.slider_edge_sens.pack(pady=(2, 5), fill="x")
        
        # Initial state for edge slider
        self.update_edge_controls_state()

        # Downsampling Method Section
        ctk.CTkLabel(self.param_frame, text="다운샘플링 정책:", anchor="w").pack(pady=(5, 0), fill="x")
        self.downsample_methods = ["Standard", "K-Means"]
        self.option_downsample = ctk.CTkOptionMenu(self.param_frame, values=self.downsample_methods, command=self.on_param_change)
        self.option_downsample.set("Standard")
        self.option_downsample.pack(pady=5, fill="x")

        # Preset Section (New)
        ctk.CTkLabel(self.param_frame, text="필터 프리셋 (Presets):", anchor="w", font=("Arial", 12, "bold")).pack(pady=(15, 0), fill="x")
        preset_frame = ctk.CTkFrame(self.param_frame, fg_color="transparent")
        preset_frame.pack(fill="x", pady=5)
        
        self.option_presets = ctk.CTkOptionMenu(preset_frame, values=["기본값 (Defaults)"], command=self.apply_preset)
        self.option_presets.set("기본값 (Defaults)")
        self.option_presets.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        self.btn_save_preset = ctk.CTkButton(preset_frame, text="💾", width=30, command=self.save_preset_dialog)
        self.btn_save_preset.pack(side="right")
        ToolTip(self.btn_save_preset, text="현재 설정을 새로운 프리셋으로 저장합니다.")

        # Magnifier Button (Saving space)
        # Magnifier Button (Saving space)
        self.btn_open_mag = ctk.CTkButton(self.param_frame, text="🔍 돋보기 열기", command=self.toggle_magnifier, fg_color="#d35400", hover_color="#e67e22")
        self.btn_open_mag.pack(pady=10, fill="x")
        self.mag_window = None

        # Status Label - Put in a fixed height container to prevent shifting
        self.status_container = ctk.CTkFrame(self.sidebar, height=30, fg_color="transparent")
        self.status_container.pack(side="bottom", pady=5, fill="x")
        self.status_container.pack_propagate(False)

        self.status_label = ctk.CTkLabel(self.status_container, text="", text_color="#2ecc71") # Greenish status
        self.status_label.pack(expand=True)

        # Save Section
        # Save Section
        self.btn_save = ctk.CTkButton(self.sidebar, text="이미지 저장 (Export Image)", command=self.save_image, state="disabled", fg_color="#2ecc71", hover_color="#27ae60", height=45, font=("Arial", 16, "bold"))
        self.btn_save.pack(side="bottom", pady=(5, 20), padx=20, fill="x")
        
        # Tooltip for Save Button
        ToolTip(self.btn_save, text="원본 형식을 유지하고 다른 이름으로 저장합니다.")

        # --- Main Preview Area ---
        self.preview_frame = ctk.CTkFrame(self, corner_radius=12, fg_color="#1a1a1a")
        self.preview_frame.grid(row=1, column=1, padx=20, pady=20, sticky="nsew")
        self.preview_frame.grid_propagate(False) # CRITICAL: Stability
        
        # Reset layout to single stable cell
        self.preview_frame.grid_columnconfigure(0, weight=1)
        self.preview_frame.grid_rowconfigure(0, weight=1)

        self.preview_canvas = ctk.CTkCanvas(self.preview_frame, bg="#1a1a1a", highlightthickness=0)
        self.preview_canvas.grid(row=0, column=0, sticky="nsew")
        
        # Palette Inspector Overlay (Over the canvas, doesn't shift layout)
        # We use place to ensure it doesn't trigger parent resize or shifting
        self.palette_inspector = PaletteInspector(self.preview_frame, width=300, height=28, 
                                                 corner_radius=6, border_width=1, border_color="#444")
        self.palette_inspector.place(relx=0.0, rely=0.0, x=15, y=15, anchor="nw")

        # Resolution Info Overlay (Top Right)
        self.res_info_frame = ctk.CTkFrame(self.preview_frame, width=120, height=28, 
                                          corner_radius=6, border_width=1, border_color="#444", fg_color="#2b2b2b")
        self.res_info_frame.place(relx=1.0, rely=0.0, x=-15, y=15, anchor="ne")
        self.res_info_frame.pack_propagate(False)
        self.res_label = ctk.CTkLabel(self.res_info_frame, text="0 x 0", font=("Consolas", 12, "bold"), text_color="#aaa")
        self.res_label.pack(expand=True)

        self.preview_canvas.bind("<MouseWheel>", self.on_preview_wheel)
        self.preview_canvas.bind("<Motion>", self.update_magnifier)
        self.preview_canvas.bind("<Configure>", self.on_resize)

        self.canvas_image_id = None
        self.tk_preview = None

        # --- Right Inventory Sidebar ---
        self.inventory_frame = ctk.CTkFrame(self, width=180, corner_radius=0)
        self.inventory_frame.grid(row=1, column=2, sticky="nsew")
        self.inventory_frame.grid_propagate(False)
        
        # Load Image Button (at top of inventory)
        self.btn_add_to_inv = ctk.CTkButton(self.inventory_frame, text="📂 이미지 추가", command=self.add_image_to_inventory, height=35, fg_color="#27ae60")
        self.btn_add_to_inv.pack(pady=10, padx=10, fill="x")
        
        self.label_inv_header = ctk.CTkLabel(self.inventory_frame, text="인벤토리 (0/256)", font=("Arial", 11))
        self.label_inv_header.pack(pady=(5, 0))
        
        # Scrollable list for inventory items
        self.inventory_scroll = ctk.CTkScrollableFrame(self.inventory_frame, width=160)
        self.inventory_scroll.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Format selection for export
        ctk.CTkLabel(self.inventory_frame, text="저장 포맷:", anchor="w").pack(pady=(5, 0), padx=10, fill="x")
        self.format_combo = ctk.CTkOptionMenu(self.inventory_frame, values=["PNG", "JPG", "BMP", "WEBP"])
        self.format_combo.set("PNG")
        self.format_combo.pack(pady=5, padx=10, fill="x")
        
        # Batch Export Button
        self.btn_batch_export = ctk.CTkButton(self.inventory_frame, text="일괄 저장 (Save All)", command=self.batch_export, height=35, fg_color="#3498db")
        self.btn_batch_export.pack(pady=10, padx=10, fill="x", side="bottom")

    def load_presets(self):
        """Loads presets from the JSON file."""
        if os.path.exists(self.presets_path):
            try:
                with open(self.presets_path, "r", encoding="utf-8") as f:
                    self.presets = json.load(f)
                
                # Update UI ComboBox
                preset_names = list(self.presets.keys())
                if preset_names:
                    self.option_presets.configure(values=preset_names)
                    # Don't set yet, keep "기본값 (Defaults)" or similar if it's not in keys
                print(f"Loaded {len(self.presets)} presets.")
            except Exception as e:
                print(f"Error loading presets: {e}")

    def apply_preset(self, preset_name):
        """Applies a selected preset to the UI."""
        if preset_name in self.presets:
            print(f"Applying preset: {preset_name}")
            self.restore_ui_state(self.presets[preset_name])

    def save_preset_dialog(self):
        """Opens a simple dialog to name and save the current preset."""
        dialog = ctk.CTkInputDialog(text="새로운 프리셋 이름을 입력하세요:", title="프리셋 저장")
        name = dialog.get_input()
        if name:
            self.presets[name] = self.capture_ui_state()
            try:
                with open(self.presets_path, "w", encoding="utf-8") as f:
                    json.dump(self.presets, f, indent=4)
                
                # Update UI
                self.option_presets.configure(values=list(self.presets.keys()))
                self.option_presets.set(name)
                print(f"Preset '{name}' saved.")
            except Exception as e:
                print(f"Error saving preset: {e}")

    def load_default_palette(self):
        path = os.path.join(self.palette_dir, "default_palette.json")
        if os.path.exists(path):
            self._load_palette_from_path(path)

    def _load_palette_from_path(self, path):
        try:
            with open(path, "r") as f:
                colors = json.load(f)
                if isinstance(colors, list) and len(colors) > 0:
                    self.user_palette_colors_persistent[:len(colors)] = [tuple(c) for c in colors]
            print(f"Palette loaded from {path}")
        except Exception as e:
            print(f"Error loading palette: {e}")

    def save_default_palette(self):
        path = os.path.join(self.palette_dir, "default_palette.json")
        self._save_palette_to_path(path)

    def _save_palette_to_path(self, path):
        try:
            with open(path, "w") as f:
                json.dump(self.user_palette_colors_persistent, f)
            print(f"Palette saved to {path}")
        except Exception as e:
            print(f"Error saving palette: {e}")

    def load_palette_file(self):
        file_path = filedialog.askopenfilename(
            parent=self,
            initialdir=self.last_palette_dir,
            filetypes=[("JSON files", "*.json")]
        )
        if file_path:
            self.last_palette_dir = os.path.dirname(file_path)
            self._load_palette_from_path(file_path)
            self.option_palette.set("USER CUSTOM")
            self.on_palette_menu_change("USER CUSTOM")

    def save_palette_file(self):
        file_path = filedialog.asksaveasfilename(
            parent=self,
            initialdir=self.last_palette_dir,
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")]
        )
        if file_path:
            self.last_palette_dir = os.path.dirname(file_path)
            self._save_palette_to_path(file_path)

    def save_project_file(self):
        if not self.original_image_path:
            return

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
        
        file_path = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".pcp",
            filetypes=[("Pixel Crafter Project", "*.pcp")]
        )
        if file_path:
            if ProjectManager.save_project(file_path, state):
                print(f"Project saved to {file_path}")

    def load_project_file(self):
        file_path = filedialog.askopenfilename(
            parent=self,
            filetypes=[("Pixel Crafter Project", "*.pcp")]
        )
        if not file_path: return

        state = ProjectManager.load_project(file_path)
        if not state: return

        # Restore State
        try:
            if "source_path" in state and os.path.exists(state["source_path"]):
                self.original_image_path = state["source_path"]
                # Re-open image
                with Image.open(self.original_image_path) as img:
                    self.original_size = img.size
                self.preview_zoom = state.get("preview_zoom", -1)
                
            if "pixel_size" in state:
                self.slider_pixel.set(state["pixel_size"])
                # No longer updating label text to maintain stability
                
            if "palette_mode" in state:
                self.option_palette.set(state["palette_mode"])
                self.on_palette_menu_change(state["palette_mode"])
                
            if "max_colors" in state:
                self.color_slider.set(state["max_colors"])
                self.color_spinbox.set(state["max_colors"])
                
            if "dither" in state:
                if state["dither"]: self.check_dither.select()
                else: self.check_dither.deselect()
                
            if "outline_enabled" in state:
                if state["outline_enabled"]: self.check_outline.select()
                else: self.check_outline.deselect()
                
            if "custom_colors" in state:
                # Convert back to tuples if loaded as lists
                self.user_palette_colors_persistent = [tuple(c) for c in state["custom_colors"]]
                
            # Trigger reprocessing
            self.process_image()
            self.btn_save.configure(state="normal")
            print(f"Project loaded from {file_path}")
            
        except Exception as e:
            print(f"Error restoring project state: {e}")

    def on_palette_menu_change(self, value):
        if value in ["Original", "GameBoy", "CGA", "Pico-8", "USER CUSTOM", "16-bit (4096 Colors)"]:
            self.color_limit_group.pack_forget()
        else:
            self.color_limit_group.pack(after=self.slider_pixel, fill="x")
            
        if value == "USER CUSTOM":
            self.active_palette_mode = "Custom_User"
            self.on_param_change()
        elif value == "16-bit (4096 Colors)":
            self.active_palette_mode = "Custom_16bit"
            self.on_param_change()
        else:
            self.active_palette_mode = "Standard"
            self.on_param_change()

    def open_custom_palette(self):
        # Pass current inspector colors as initial if available
        CustomPaletteWindow(self, self.on_custom_palette_applied, initial_colors=self.palette_inspector.colors)

    def on_custom_palette_applied(self, mode, colors):
        if colors:
            self.user_palette_colors_persistent[:len(colors)] = colors
            # If we got fewer than 16, keep the rest as black or previous? 
            # Consistent with component.py, but here we just update persistent state.
            self.save_default_palette()
        
        # Ensure 'USER CUSTOM' is selected and triggered
        self.active_palette_mode = "Custom_User"
        self.option_palette.set("USER CUSTOM")
        self.on_palette_menu_change("USER CUSTOM") # This calls on_param_change()

    def update_pixel_from_slider(self, value):
        self.pixel_spin.set(int(value))
        self.on_param_change()
        
    def update_pixel_from_spinbox(self):
        val = self.pixel_spin.get()
        if val is not None:
            self.slider_pixel.set(val)
            self.on_param_change()

    def update_color_from_slider(self, value):
        val = int(value)
        self.color_spinbox.set(val)
        self.on_param_change()

    def update_color_from_spinbox(self):
        val = self.color_spinbox.get()
        if val is not None:
            val = max(2, min(256, val))
            self.color_spinbox.set(val)
            self.color_slider.set(val)
            self.on_param_change()

    def zoom_in(self):
        if self.mag_zoom < 8:
            self.mag_zoom += 1
            self.update_zoom_ui()

    def zoom_out(self):
        if self.mag_zoom > 2:
            self.mag_zoom -= 1
            self.update_zoom_ui()

    def update_zoom_ui(self):
        self.label_zoom_val.configure(text=f"{self.mag_zoom}x")

    def update_edge_sens_label(self, value):
        self.label_edge_sens.configure(text=f"{float(value):.1f}")
        self.on_param_change()

    def on_edge_enhance_toggle(self):
        self.update_edge_controls_state()
        self.on_param_change()

    def update_edge_controls_state(self):
        if self.check_edge_enhance.get():
            self.slider_edge_sens.configure(state="normal", progress_color=["#3B8ED0", "#1F6AA5"])
            self.label_edge_sens.configure(text_color=["#000000", "#ffffff"])
        else:
            self.slider_edge_sens.configure(state="disabled", progress_color="gray")
            self.label_edge_sens.configure(text_color="gray")

    def on_setting_mode_change(self, value):
        if value == "Individual" and self.current_inventory_id is not None:
            # Capture current UI as the individual state for the selected image
            entry = self.image_manager.get_image(self.current_inventory_id)
            if entry and entry["params"] is None:
                entry["params"] = self.capture_ui_state()
        print(f"Setting Mode changed to: {value}")

    def capture_ui_state(self):
        """Captures all relevant UI parameters into a dictionary."""
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
            "custom_colors": list(self.user_palette_colors_persistent) # Snapshot
        }

    def restore_ui_state(self, params):
        """Restores UI parameters from a dictionary."""
        if not params: return
        
        # Block on_param_change from triggering multiple times
        # We can do this by setting a flag or just letting it trigger once at the end.
        # But some widgets like OptionMenu or SegmentedButton trigger command on .set() or manual select.
        # CTK widgets usually don't trigger command on .set() but let's be careful.
        
        try:
            if "save_mode" in params:
                self.mode_switch.set(params["save_mode"])
            
            if "pixel_size" in params:
                self.slider_pixel.set(params["pixel_size"])
                self.pixel_spin.set(params["pixel_size"])
                
            if "color_count" in params:
                self.color_slider.set(params["color_count"])
                self.color_spinbox.set(params["color_count"])
                
            if "palette_mode" in params:
                self.option_palette.set(params["palette_mode"])
                self.on_palette_menu_change(params["palette_mode"])
                
            if "dither" in params:
                if params["dither"]: self.check_dither.select()
                else: self.check_dither.deselect()
                
            if "remove_bg" in params:
                if params["remove_bg"]: self.check_remove_bg.select()
                else: self.check_remove_bg.deselect()
                
            if "outline" in params:
                if params["outline"]: self.check_outline.select()
                else: self.check_outline.deselect()
                
            if "edge_enhance" in params:
                if params["edge_enhance"]: self.check_edge_enhance.select()
                else: self.check_edge_enhance.deselect()
                self.update_edge_controls_state()
                
            if "edge_sensitivity" in params:
                self.slider_edge_sens.set(params["edge_sensitivity"])
                self.label_edge_sens.configure(text=f"{params['edge_sensitivity']:.1f}")
                
            if "downsample_method" in params:
                self.option_downsample.set(params["downsample_method"])
                
            if "custom_colors" in params:
                self.user_palette_colors_persistent = [tuple(c) for c in params["custom_colors"]]
                
            # Trigger one final process
            self.on_param_change()
            
        except Exception as e:
            print(f"Error restoring UI state: {e}")

    def on_param_change(self, *args):
        if self.current_inventory_id is not None:
            # If in individual mode, save current UI state to the selected item
            if self.setting_mode_switch.get() == "Individual":
                entry = self.image_manager.get_image(self.current_inventory_id)
                if entry:
                    entry["params"] = self.capture_ui_state()
            
            # Re-select (or just process) to trigger processing on correct image
            img_entry = self.image_manager.get_image(self.current_inventory_id)
            if img_entry:
                self.process_inventory_image(img_entry["pil_image"])
        elif self.original_image_path:
            self.process_image()

    def select_inventory_image(self, image_id):
        # If switching AWAY from an image in individual mode, we already saved on param change.
        # But what if we just selected it and changed nothing?
        # Actually, saving on every change is safer.
        
        self.current_inventory_id = image_id
        img_entry = self.image_manager.get_image(image_id)
        if img_entry:
            # Handle Individual Setting Mode
            if self.setting_mode_switch.get() == "Individual":
                if img_entry["params"]:
                    self.restore_ui_state(img_entry["params"])
                else:
                    # First time selecting this image in individual mode
                    # Use current UI state as its starting point
                    img_entry["params"] = self.capture_ui_state()
                    self.process_inventory_image(img_entry["pil_image"])
            else:
                # Global mode: just process with current UI
                self.process_inventory_image(img_entry["pil_image"])

    def open_image(self):
        file_path = filedialog.askopenfilename(
            parent=self,
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.webp *.gif *.bmp")]
        )
        if file_path:
            self.original_image_path = file_path
            with Image.open(file_path) as img:
                self.original_size = img.size
            self.preview_zoom = -1 
            self.process_image()
            self.btn_save.configure(state="normal")

    def process_image(self):
        """Unified entry point for processing original image path."""
        if not self.original_image_path:
            return
        self._start_threaded_process("path", self.original_image_path)

    def _start_threaded_process(self, source_type, source_data):
        """Starts a background thread for image processing to keep UI responsive."""
        if self._is_processing:
            self._pending_reprocess = True
            self._pending_source = (source_type, source_data)
            return
            
        self._is_processing = True
        self.status_label.configure(text="⏳ 처리 중 (Processing)...")
        self.btn_save.configure(state="disabled")

        # Capture parameters in UI thread
        params = {
            "pixel_size": int(self.slider_pixel.get()),
            "dither": self.check_dither.get(),
            "max_colors": int(self.color_slider.get()),
            "edge_enhance": self.check_edge_enhance.get(),
            "edge_sensitivity": float(self.slider_edge_sens.get()),
            "palette_choice": self.option_palette.get(),
            "downsample_method": self.option_downsample.get(),
            "outline": self.check_outline.get(),
            "user_pal": self.user_palette_colors_persistent,
            "remove_bg": self.check_remove_bg.get()
        }

        def run():
            try:
                # 1. PIXELATE (Heavy step)
                if source_type == "path":
                    # For path-based processing
                    with Image.open(source_data) as tmp_img:
                        self.original_size = tmp_img.size
                    
                    raw = pixelate_image(
                        source_data, 
                        params["pixel_size"], 
                        edge_enhance=params["edge_enhance"], 
                        edge_sensitivity=params["edge_sensitivity"], 
                        downsample_method=params["downsample_method"],
                        remove_bg=params["remove_bg"]
                    )
                else:
                    # For PIL-based processing (inventory)
                    img = source_data.convert("RGBA")
                    self.original_size = img.size
                    
                    # Apply BG Remove if requested
                    if params["remove_bg"]:
                         img = remove_background(img, tolerance=40)

                    # Manual pipeline steps for PIL source
                    from core.processor import enhance_internal_edges, downsample_kmeans_adaptive
                    if params["edge_enhance"] and params["edge_sensitivity"] > 0:
                        img = enhance_internal_edges(img, params["edge_sensitivity"])
                    
                    small_w = max(1, img.size[0] // params["pixel_size"])
                    small_h = max(1, img.size[1] // params["pixel_size"])
                    
                    if params["downsample_method"] == "K-Means":
                        raw = downsample_kmeans_adaptive(img, params["pixel_size"], small_w, small_h)
                    else:
                        raw = img.resize((small_w, small_h), resample=Image.BOX)

                if not raw:
                    self.after(0, self._on_processing_complete, None)
                    return

                # 2. APPLY PALETTE
                if params["palette_choice"] == "USER CUSTOM":
                    p_name, p_param = "Custom_User", params["user_pal"]
                elif params["palette_choice"] == "16-bit (4096 Colors)":
                    p_name, p_param = "Custom_16bit", None
                else:
                    p_name, p_param = params["palette_choice"], params["max_colors"]
                
                # Custom 16-bit logic (Algorithmic) is handled inside apply_palette_unified via fallback?
                # Actually our new unified pipeline handles 'Custom_16bit' returning None target,
                # so we need to handle it or ensure palette.py handles it.
                # In palette.py we left Custom_16bit returning None target. 
                # Let's handle it here or modify palette.py?
                # Wait, better to let palette.py handle it fully to keep app.py clean.
                # But looking at palette.py I wrote:
                # elif palette_name == "Custom_16bit": return None, False
                # And in Apply: if target_palette: ... else: ...
                # We need to implement the 16bit math logic there.
                
                # Let's QUICKLY Fix palette.py 16bit logic first? 
                # No, I can insert the logic in palette.py now or handle it via a revision.
                # Let's assume I will fix palette.py in next tool call or usage.
                # Actually, I missed implementing the 16bit math in the 'else' block of palette.py.
                # I should re-write palette.py to include 16bit math.
                
                processed = apply_palette_unified(raw, p_name, custom_colors=p_param, dither=params["dither"])
                
                # 3. ADD OUTLINE
                if params["outline"]:
                    processed = add_outline(processed)
                
                # 4. PREVIEW UPSCALE
                preview = upscale_for_preview(processed, self.original_size)
                
                # Update state and UI
                self.after(0, self._on_processing_complete, processed, preview)
                
            except Exception as e:
                print(f"Error in processing thread: {e}")
                self.after(0, self._on_processing_complete, None)

        threading.Thread(target=run, daemon=True).start()

    def _on_processing_complete(self, processed_img, preview_img=None):
        """Final UI updates after thread completion."""
        self._is_processing = False
        self.status_label.configure(text="")
        
        if processed_img:
            self.raw_pixel_image = processed_img
            self.preview_image = preview_img
            self.display_image()
            self.btn_save.configure(state="normal")
            
            # Update Palette Inspector
            # Extract predominant colors (up to 16)
            try:
                # We need extensive colors for inspector. 
                # processed_img might be RGB (if from quantize). 
                # Fast way to get colors.
                # Extract colors for inspector
                colors = self.extract_used_colors(processed_img)
                self.palette_inspector.update_colors(colors)
                
                # Update resolution label based on mode
                if self.mode_switch.get() == "Pixelate":
                    rw, rh = processed_img.size
                else:
                    rw, rh = self.original_size
                self.res_label.configure(text=f"{rw} x {rh}")
            except Exception as e:
                print(f"Inspector update failed: {e}")
        
        # Check for pending requests that happened during processing
        if self._pending_reprocess:
            self._pending_reprocess = False
            s_type, s_data = self._pending_source
            self._start_threaded_process(s_type, s_data)

    def extract_used_colors(self, pil_img):
        """
        Extracts up to 16 predominant colors from the image.
        Returns a list of RGB tuples (0-255).
        """
        # Convert to RGB to ensure we can get colors
        temp_img = pil_img.convert("RGB")
        # getcolors returns (count, (r,g,b))
        # maxcolors should be high enough to catch all in low-bit modes
        colors = temp_img.getcolors(maxcolors=4096)
        if not colors:
            return []
            
        # Sort by count (most frequent first)
        sorted_colors = sorted(colors, key=lambda x: x[0], reverse=True)
        # Extract just the RGB part, limiting to 16
        return [c[1] for c in sorted_colors[:16]]

    def display_image(self):
        if not self.preview_image: return
        cw = self.preview_canvas.winfo_width()
        ch = self.preview_canvas.winfo_height()
        if cw <= 1: cw, ch = 800, 600
        iw, ih = self.preview_image.size
        
        if self.preview_zoom == -1:
            self.preview_zoom = min(cw / iw, ch / ih) * 0.9

        nw, nh = int(iw * self.preview_zoom), int(ih * self.preview_zoom)
        display_img = self.preview_image.resize((nw, nh), Image.NEAREST)
        
        self.tk_preview = ImageTk.PhotoImage(display_img)
        if self.canvas_image_id:
            self.preview_canvas.delete(self.canvas_image_id)
        
        self.canvas_image_id = self.preview_canvas.create_image(cw//2, ch//2, image=self.tk_preview, anchor="center")

    def on_preview_wheel(self, event):
        if not self.preview_image: return
        scale_factor = 1.1 if event.delta > 0 else 0.9
        self.preview_zoom *= scale_factor
        self.preview_zoom = max(0.1, min(20.0, self.preview_zoom))
        self.display_image()

    def on_resize(self, event):
        if self.preview_image:
            self.display_image()

    def toggle_magnifier(self):
        from ui.components import MagnifierWindow # Delayed import to avoid circular dependency if any, or just ensure it exists
        if self.mag_window is None or not self.mag_window.winfo_exists():
            self.mag_window = MagnifierWindow(self)
        else:
            self.mag_window.focus()

    def update_magnifier(self, event):
        if not self.preview_image or not self.canvas_image_id: return
        if not (self.mag_window and self.mag_window.winfo_exists()): return
        
        cw = self.preview_canvas.winfo_width()
        ch = self.preview_canvas.winfo_height()
        iw, ih = self.preview_image.size
        nw, nh = int(iw * self.preview_zoom), int(ih * self.preview_zoom)
        
        img_x = event.x - (cw//2 - nw//2)
        img_y = event.y - (ch//2 - nh//2)
        
        src_x = int(img_x / self.preview_zoom)
        src_y = int(img_y / self.preview_zoom)
        if not (0 <= src_x < iw and 0 <= src_y < ih): return

        self.mag_window.update_zoom(self.preview_image, (src_x, src_y), self.mag_zoom)

    def save_image(self):
        # Determine the source path from current inventory item if available
        src_path = self.original_image_path
        if self.current_inventory_id is not None:
            entry = self.image_manager.get_image(self.current_inventory_id)
            if entry:
                src_path = entry["path"]
                
        if not src_path: return
        
        is_gif = src_path.lower().endswith('.gif')
        
        filetypes = [("PNG file", "*.png")]
        def_ext = ".png"
        
        if is_gif:
            filetypes.insert(0, ("GIF Animation", "*.gif"))
            def_ext = ".gif"
            
        file_path = filedialog.asksaveasfilename(parent=self, defaultextension=def_ext, filetypes=filetypes)
        
        if file_path:
            # Check if saving as GIF
            if is_gif and file_path.lower().endswith('.gif'):
                # Gather params for GIF processing
                pixel_size = int(self.slider_pixel.get())
                dither = self.check_dither.get()
                max_colors_val = int(self.color_slider.get())
                
                palette_choice = self.option_palette.get()
                if palette_choice == "USER CUSTOM":
                    palette_name = "Custom_User"
                    p_param = self.user_palette_colors_persistent
                elif palette_choice == "16-bit (4096 Colors)":
                    palette_name = "Custom_16bit"
                    p_param = None
                else:
                    palette_name = palette_choice
                    p_param = max_colors_val
                
                self.btn_save.configure(text="Processing GIF...", state="disabled")
                self.update() # Force UI update
                
                outline_enabled = self.check_outline.get()
                success, count = process_gif(src_path, file_path, pixel_size, palette_name, p_param, dither, outline_enabled)
                
                self.btn_save.configure(text="이미지 저장 (Export Image)", state="normal")
                
                if success:
                    print(f"Exported Animated GIF with {count} frames to: {file_path}")
                else:
                    print("Failed to export GIF.")
            else:
                # Normal static save
                if self.mode_switch.get() == "Pixelate":
                    if self.raw_pixel_image:
                        self.raw_pixel_image.save(file_path)
                else:
                    if self.preview_image:
                        self.preview_image.save(file_path)
                print(f"Export Finished: {file_path}")

    # --- Inventory Methods ---
    def add_image_to_inventory(self):
        file_paths = filedialog.askopenfilenames(
            parent=self,
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.webp *.gif *.bmp")]
        )
        new_ids = []
        for path in file_paths:
            added = self.image_manager.add_image(path)
            new_ids.extend(added)
            
        # Add only new widgets to inventory
        for img_id in new_ids:
            img_entry = self.image_manager.get_image(img_id)
            if img_entry:
                self._create_inventory_item(img_entry)
        
        self.update_inventory_count_label()
        
        # If first image added and nothing displayed, show it
        if self.image_manager.count() > 0 and self.current_inventory_id is None:
            first_img = self.image_manager.get_all()[0]
            self.select_inventory_image(first_img["id"])

    def update_inventory_count_label(self):
        # Update count label
        for widget in self.inventory_frame.winfo_children():
            if isinstance(widget, ctk.CTkLabel) and "인벤토리" in widget.cget("text"):
                widget.configure(text=f"인벤토리 ({self.image_manager.count()}/256)")
                break

    def refresh_inventory_ui(self):
        """Full refresh (used for startup or major changes)."""
        # Clear existing
        for widget in list(self.inventory_widgets.values()):
            widget.destroy()
        self.inventory_widgets.clear()
        
        for img_entry in self.image_manager.get_all():
            self._create_inventory_item(img_entry)
        self.update_inventory_count_label()

    def _create_inventory_item(self, img_entry):
        image_id = img_entry["id"]
        item_frame = ctk.CTkFrame(self.inventory_scroll, height=70, fg_color="#2a2a2a", corner_radius=8)
        item_frame.pack(fill="x", pady=3, padx=2)
        item_frame.pack_propagate(False)
        self.inventory_widgets[image_id] = item_frame
        
        # Thumbnail
        thumb = img_entry["thumbnail"]
        ctk_thumb = ctk.CTkImage(light_image=thumb, dark_image=thumb, size=(50, 50))
        thumb_label = ctk.CTkLabel(item_frame, image=ctk_thumb, text="")
        thumb_label.pack(side="left", padx=5, pady=5)
        thumb_label.image = ctk_thumb  # Keep reference
        
        # Name
        name_label = ctk.CTkLabel(item_frame, text=img_entry["name"][:12], font=("Arial", 10), anchor="w")
        name_label.pack(side="left", fill="x", expand=True, padx=5)
        
        # Delete button (hidden by default, shown on hover)
        del_btn = ctk.CTkButton(item_frame, text="X", width=20, height=20, fg_color="#e74c3c", 
                                command=lambda id=img_entry["id"]: self.remove_from_inventory(id))
        del_btn.place(relx=1.0, rely=0, anchor="ne", x=-5, y=5)
        del_btn.lower()  # Hide initially
        
        # Hover events
        def on_enter(e):
            del_btn.lift()
        def on_leave(e):
            del_btn.lower()
            
        item_frame.bind("<Enter>", on_enter)
        item_frame.bind("<Leave>", on_leave)
        
        # Click to select
        item_frame.bind("<Button-1>", lambda e, id=img_entry["id"]: self.select_inventory_image(id))
        thumb_label.bind("<Button-1>", lambda e, id=img_entry["id"]: self.select_inventory_image(id))
        name_label.bind("<Button-1>", lambda e, id=img_entry["id"]: self.select_inventory_image(id))

    def remove_from_inventory(self, image_id):
        # Destroy specific widget to avoid full refresh flicker
        if image_id in self.inventory_widgets:
            self.inventory_widgets[image_id].destroy()
            del self.inventory_widgets[image_id]
            
        self.image_manager.remove_image(image_id)
        self.update_inventory_count_label()
        
        # If removed current, reset
        if self.current_inventory_id == image_id:
            self.current_inventory_id = None
            if self.image_manager.count() > 0:
                self.select_inventory_image(self.image_manager.get_all()[0]["id"])

    def select_inventory_image(self, image_id):
        self.current_inventory_id = image_id
        img_entry = self.image_manager.get_image(image_id)
        if img_entry:
            # Process and display this image using current settings
            self.process_inventory_image(img_entry["pil_image"])

    def process_inventory_image(self, pil_image):
        """Unified entry point for processing an image from inventory."""
        self._start_threaded_process("pil", pil_image)

    def batch_export(self):
        if self.image_manager.count() == 0:
            return
            
        # Ask for output folder
        output_dir = filedialog.askdirectory(parent=self, title="일괄 저장 폴더 선택")
        if not output_dir:
            return
        
        export_format = self.format_combo.get().lower()
        
        # Capture current Global settings as fallback
        global_params = self.capture_ui_state()
        setting_mode = self.setting_mode_switch.get()
        
        from core.processor import enhance_internal_edges, remove_background
        from core.palette import apply_palette_unified
        
        count = 0
        for img_entry in self.image_manager.get_all():
            try:
                # Determine which parameters to use
                if setting_mode == "Individual" and img_entry["params"]:
                    p = img_entry["params"]
                else:
                    p = global_params
                
                pil_img = img_entry["pil_image"].convert("RGBA")
                
                # BG Removal
                if p.get("remove_bg", False):
                    pil_img = remove_background(pil_img)

                # Edge enhancement
                if p.get("edge_enhance", False) and p.get("edge_sensitivity", 1.0) > 0:
                    pil_img = enhance_internal_edges(pil_img, p["edge_sensitivity"])
                
                # Downsample
                pixel_size = p.get("pixel_size", 8)
                small_w = max(1, pil_img.size[0] // pixel_size)
                small_h = max(1, pil_img.size[1] // pixel_size)
                
                # Note: Batch export currently uses BOX resize. 
                # We could support K-Means here too if needed.
                # For consistency with current batch_export logic, sticking to BOX but using params.
                small_img = pil_img.resize((small_w, small_h), resample=Image.BOX)
                
                # Apply palette
                pal_choice = p.get("palette_mode", "Limited")
                if pal_choice == "USER CUSTOM":
                    p_name, p_param = "Custom_User", p.get("custom_colors")
                elif pal_choice == "16-bit (4096 Colors)":
                    p_name, p_param = "Custom_16bit", None
                else:
                    p_name, p_param = pal_choice, p.get("color_count", 16)
                
                processed = apply_palette_unified(small_img, p_name, custom_colors=p_param, dither=p.get("dither", True))
                
                # Outline
                if p.get("outline", False):
                    processed = add_outline(processed)
                
                # Upscale (always to original size for batch export)
                final = processed.resize(img_entry["pil_image"].size, resample=Image.NEAREST)
                
                # Handle format-specific conversion
                if export_format in ["jpg", "bmp"]:
                    # These formats don't support transparency
                    final = final.convert("RGB")
                
                # Save
                filename = f"{img_entry['name']}_pixel.{export_format}"
                save_path = os.path.join(output_dir, filename)
                final.save(save_path)
                count += 1
                
            except Exception as e:
                print(f"Error processing {img_entry['name']}: {e}")
        
        print(f"Batch export completed: {count} images saved to {output_dir}")

class MagnifierWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("🔍 Pixel Magnifier")
        self.geometry("300x380")
        self.attributes("-topmost", True)
        
        self.parent = parent
        
        # Display Area
        self.display_label = ctk.CTkLabel(self, text="", width=280, height=280, fg_color="black", corner_radius=10)
        self.display_label.pack(pady=10, padx=10)
        
        # Zoom Controls
        control_frame = ctk.CTkFrame(self, fg_color="transparent")
        control_frame.pack(pady=5, fill="x", padx=10)
        
        ctk.CTkButton(control_frame, text="-", width=40, command=self.zoom_out).pack(side="left", padx=5)
        self.label_zoom = ctk.CTkLabel(control_frame, text=f"{self.parent.mag_zoom}x", font=("Arial", 16, "bold"))
        self.label_zoom.pack(side="left", expand=True)
        ctk.CTkButton(control_frame, text="+", width=40, command=self.zoom_in).pack(side="left", padx=5)
        
        ctk.CTkLabel(self, text="Mouse over preview area", font=("Arial", 10, "italic")).pack(pady=5)

    def zoom_in(self):
        if self.parent.mag_zoom < 16:
            self.parent.mag_zoom += 1
            self.label_zoom.configure(text=f"{self.parent.mag_zoom}x")

    def zoom_out(self):
        if self.parent.mag_zoom > 2:
            self.parent.mag_zoom -= 1
            self.label_zoom.configure(text=f"{self.parent.mag_zoom}x")

    def update_zoom(self, full_image, center_pos, zoom_level):
        mag_display_size = (280, 280)
        source_area_size = max(1, int(mag_display_size[0] / zoom_level))
        
        iw, ih = full_image.size
        src_x, src_y = center_pos
        
        left = max(0, src_x - source_area_size // 2)
        top = max(0, src_y - source_area_size // 2)
        right = min(iw, left + source_area_size)
        bottom = min(ih, top + source_area_size)
        
        crop = full_image.crop((left, top, right, bottom))
        crop_rescaled = crop.resize(mag_display_size, Image.NEAREST)
        
        ctk_mag = ctk.CTkImage(light_image=crop_rescaled, dark_image=crop_rescaled, size=mag_display_size)
        self.display_label.configure(image=ctk_mag, text="")
        self.display_label.image = ctk_mag

if __name__ == "__main__":
    app = PixelApp()
    app.mainloop()
