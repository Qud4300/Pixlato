import customtkinter as ctk
from tkinter import filedialog
from core.palette_parser import PaletteParser

class IntSpinbox(ctk.CTkFrame):
    def __init__(self, *args, width=100, height=32, step_size=1, from_=0, to=256, command=None, **kwargs):
        super().__init__(*args, width=width, height=height, **kwargs)

        self.step_size = step_size
        self.from_ = from_
        self.to = to
        self.command = command

        self.grid_columnconfigure((0, 2), weight=0)
        self.grid_columnconfigure(1, weight=1)

        self.subtract_button = ctk.CTkButton(self, text="-", width=height-6, height=height-6,
                                               command=self.subtract_button_callback)
        self.subtract_button.grid(row=0, column=0, padx=(3, 0), pady=3)

        self.entry = ctk.CTkEntry(self, width=width-(2*height), height=height-6, border_width=0)
        self.entry.grid(row=0, column=1, columnspan=1, padx=3, pady=3, sticky="ew")

        self.add_button = ctk.CTkButton(self, text="+", width=height-6, height=height-6,
                                          command=self.add_button_callback)
        self.add_button.grid(row=0, column=2, padx=(0, 3), pady=3)

        # default value
        self.entry.insert(0, "16")

    def add_button_callback(self):
        try:
            value = int(self.entry.get()) + self.step_size
            if value <= self.to:
                self.entry.delete(0, "end")
                self.entry.insert(0, value)
                if self.command is not None:
                    self.command()
        except ValueError:
            return

    def subtract_button_callback(self):
        try:
            value = int(self.entry.get()) - self.step_size
            if value >= self.from_:
                self.entry.delete(0, "end")
                self.entry.insert(0, value)
                if self.command is not None:
                    self.command()
        except ValueError:
            return

    def get(self):
        try:
            return int(self.entry.get())
        except ValueError:
            return None

    def set(self, value):
        self.entry.delete(0, "end")
        self.entry.insert(0, str(value))

class ToolTip(ctk.CTkToplevel):
    """
    A simple ToolTip widget for CustomTkinter.
    """
    def __init__(self, widget, text, delay=300):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tip_window = None
        self.id = None
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.widget.bind("<ButtonPress>", self.leave)

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(self.delay, self.showtip)

    def unschedule(self):
        id = self.id
        self.id = None
        if id:
            self.widget.after_cancel(id)

    def showtip(self, event=None):
        x = y = 0
        x, y, cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        
        # Creates a toplevel window
        self.tip_window = ctk.CTkToplevel(self.widget)
        self.tip_window.wm_overrideredirect(True)
        self.tip_window.wm_geometry("+%d+%d" % (x, y))
        
        label = ctk.CTkLabel(self.tip_window, text=self.text, justify='left',
                             fg_color="#333333", text_color="#ffffff",
                             corner_radius=6, font=("Arial", 12))
        label.pack(ipadx=10, ipady=5)
        
        # Ensure it's on top but doesn't take focus
        self.tip_window.attributes("-topmost", True)
        self.tip_window.attributes("-alpha", 0.9)

    def hidetip(self):
        tw = self.tip_window
        self.tip_window = None
        if tw:
            tw.destroy()

class PaletteInspector(ctk.CTkFrame):
    """
    A widget to visualize a list of colors (RGB tuples).
    """
    def __init__(self, parent, width=200, height=30, click_callback=None, **kwargs):
        super().__init__(parent, width=width, height=height, **kwargs)
        self.pack_propagate(False) # Prevent size changes based on content
        self.canvas = ctk.CTkCanvas(self, width=width, height=height, highlightthickness=0, bg="#2b2b2b", cursor="hand2")
        self.canvas.pack(fill="both", expand=True)
        self.colors = []
        self.click_callback = click_callback
        self.canvas.bind("<Button-1>", self.on_click)

    def on_click(self, event):
        if not self.colors or not self.click_callback:
            return
        
        w = self.canvas.winfo_width()
        display_colors = self.colors[:16]
        count = len(display_colors)
        if count == 0: return

        slot_w = w / count
        index = int(event.x // slot_w)
        
        if 0 <= index < count:
            self.click_callback(index, self.colors[index])

    def update_colors(self, colors):
        """
        Updates the visualization with a list of RGB tuples (0-255).
        """
        self.colors = colors
        self.canvas.delete("all")
        
        if not colors:
            return

        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        # Use initial width if not yet rendered to avoid jitter
        if w <= 1: w = self.cget("width")
        if h <= 1: h = self.cget("height")
        
        # We want to show up to 16 colors. 
        # If more, truncate. If less, just show them.
        display_colors = colors[:16]
        count = len(display_colors)
        if count == 0: return

        slot_w = w / count
        
        for i, color in enumerate(display_colors):
            hex_c = "#{:02x}{:02x}{:02x}".format(*color)
            x0 = i * slot_w
            x1 = (i + 1) * slot_w
            self.canvas.create_rectangle(x0, 0, x1, h, fill=hex_c, outline="", tags="color")
            
            # Optional: Add tooltip-like behavior on click or hover? 
            # For now just visual.

from PIL import Image, ImageDraw, ImageTk
import colorsys

class CustomPaletteWindow(ctk.CTkToplevel):
    def __init__(self, parent, current_callback, initial_colors=None, initial_index=0, live_callback=None):
        super().__init__(parent)
        self.title("커스텀 팔레트 설정 (Custom Palette)")
        self.geometry("820x720") 
        self.resizable(False, False)
        self.parent = parent
        self.current_callback = current_callback
        self.live_callback = live_callback
        
        # Modal behavior
        self.transient(parent)
        self.focus_force()

        # State Persistence: Normalize to exactly 16 slots to prevent IndexError
        if initial_colors:
            self.persistent_colors = list(initial_colors[:16])
            if len(self.persistent_colors) < 16:
                self.persistent_colors.extend([(0, 0, 0)] * (16 - len(self.persistent_colors)))
        else:
            self.persistent_colors = [(0, 0, 0)] * 16
        
        self.bit_mode = ctk.StringVar(value="4bit")
        self.current_slot_index = initial_index
        self.current_h = 0.0
        self.current_s = 1.0
        self.current_v = 1.0

        # Layout
        self.grid_columnconfigure(0, weight=0) # Left Sidebar
        self.grid_columnconfigure(1, weight=1) # Right Area
        self.grid_rowconfigure(0, weight=1)

        # --- LEFT SIDEBAR ---
        self.left_sidebar = ctk.CTkFrame(self, width=350)
        self.left_sidebar.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)

        ctk.CTkLabel(self.left_sidebar, text="비트 모드 선택", font=("Arial", 18, "bold")).pack(pady=(20, 10))
        
        self.radio_frame = ctk.CTkFrame(self.left_sidebar, fg_color="transparent")
        self.radio_frame.pack(pady=5, padx=20, fill="x")
        
        # We need to preserve current results when switching
        self.radio_2bit = ctk.CTkRadioButton(self.radio_frame, text="2-bit (4색)", variable=self.bit_mode, value="2bit", command=self.update_bit_ui)
        self.radio_2bit.pack(pady=8, anchor="w")
        self.radio_4bit = ctk.CTkRadioButton(self.radio_frame, text="4-bit (16색)", variable=self.bit_mode, value="4bit", command=self.update_bit_ui)
        self.radio_4bit.pack(pady=8, anchor="w")

        ctk.CTkLabel(self.left_sidebar, text="컬러 슬롯 (클릭하여 선택)", font=("Arial", 14, "bold")).pack(pady=(30, 5))
        self.slot_frame = ctk.CTkFrame(self.left_sidebar, fg_color="#121212", corner_radius=12)
        self.slot_frame.pack(pady=5, padx=20, fill="both", expand=True)
        
        self.slots_container = ctk.CTkFrame(self.slot_frame, fg_color="transparent")
        self.slots_container.pack(pady=10, padx=10)
        
        self.slots = []
        
        self.btn_add_color = ctk.CTkButton(self.left_sidebar, text="현재 색상을 슬롯에 추가", command=self.add_current_color, 
                                            font=("Arial", 14, "bold"), height=32)
        self.btn_add_color.pack(pady=10, padx=20, fill="x")

        # --- Pro Tools Section ---
        ctk.CTkLabel(self.left_sidebar, text="고급 도구 (Pro Tools)", font=("Arial", 14, "bold")).pack(pady=(10, 5))
        self.tools_frame = ctk.CTkFrame(self.left_sidebar, fg_color="transparent")
        self.tools_frame.pack(pady=5, padx=20, fill="x")

        self.btn_import_file = ctk.CTkButton(self.tools_frame, text="📁 팔레트 파일 불러오기", 
                                             command=self.import_palette_file, height=30, fg_color="#555", font=("Arial", 12))
        self.btn_import_file.pack(pady=3, fill="x")

        self.btn_extract_img = ctk.CTkButton(self.tools_frame, text="🎨 원본 이미지에서 추출", 
                                             command=self.extract_palette_from_image, height=30, fg_color="#555", font=("Arial", 12))
        self.btn_extract_img.pack(pady=3, fill="x")

        # --- RIGHT AREA ---
        self.picker_frame = ctk.CTkFrame(self)
        self.picker_frame.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)
        
        ctk.CTkLabel(self.picker_frame, text="상세 색상 피커", font=("Arial", 20, "bold")).pack(pady=10)
        
        # Reduced canvas size: 336x336 (20% reduction from 420)
        self.canvas_size = 336
        self.sv_canvas = ctk.CTkCanvas(self.picker_frame, width=self.canvas_size, height=self.canvas_size, highlightthickness=1, cursor="cross", highlightbackground="#444")
        self.sv_canvas.pack(pady=5)
        self.sv_canvas.bind("<B1-Motion>", self.on_sv_click)
        self.sv_canvas.bind("<Button-1>", self.on_sv_click)
        self.sv_canvas.bind("<Motion>", self.on_sv_hover)

        # Hue Pointer Area
        self.hue_pointer_frame = ctk.CTkFrame(self.picker_frame, fg_color="transparent")
        self.hue_pointer_frame.pack(fill="x", padx=40, pady=(10, 0))
        
        self.hue_pointer_canvas = ctk.CTkCanvas(self.hue_pointer_frame, height=20, highlightthickness=0, bg="#2b2b2b")
        self.hue_pointer_canvas.pack(fill="x")
        
        self.hue_slider = ctk.CTkSlider(self.picker_frame, from_=0, to=1, command=self.on_hue_change, height=15)
        self.hue_slider.set(0)
        self.hue_slider.pack(fill="x", padx=40, pady=(0, 5))

        self.hue_info_frame = ctk.CTkFrame(self.picker_frame, fg_color="transparent")
        self.hue_info_frame.pack(fill="x", padx=40)
        
        self.hue_hex_label = ctk.CTkLabel(self.hue_info_frame, text="Hue Hex: #FF0000", font=("Consolas", 12))
        self.hue_hex_label.pack(side="right")
        
        self.after(100, self.update_hue_pointer)

        # Visual Feedback
        self.preview_group = ctk.CTkFrame(self.picker_frame, fg_color="transparent")
        self.preview_group.pack(pady=10)
        
        self.current_color_preview = ctk.CTkLabel(self.preview_group, text="", width=100, height=50, fg_color="#ff0000", corner_radius=8)
        self.current_color_preview.pack(side="left", padx=10)
        
        self.info_text_frame = ctk.CTkFrame(self.preview_group, fg_color="transparent")
        self.info_text_frame.pack(side="left", padx=10)

        self.hex_label = ctk.CTkLabel(self.info_text_frame, text="Current: #FF0000", font=("Consolas", 16, "bold"))
        self.hex_label.pack(anchor="w")
        
        self.cursor_hex_label = ctk.CTkLabel(self.info_text_frame, text="Cursor: #FF0000", font=("Consolas", 14), text_color="#aaa")
        self.cursor_hex_label.pack(anchor="w")

        self.btn_apply = ctk.CTkButton(self.picker_frame, text="✅ 팔레트 적용 및 닫기", command=self.apply_to_main, 
                                        fg_color="#27ae60", hover_color="#219150", height=45, font=("Arial", 16, "bold"))
        self.btn_apply.pack(pady=(10, 20), padx=80, fill="x", side="bottom")

        self.init_slots()
        self.draw_sv_gradient()
        self.update_bit_ui()
        
        # Ensure focus
        self.attributes("-topmost", True)
        self.grab_set()
        
        # Handle manual window closing
        self.protocol("WM_DELETE_WINDOW", self.close_without_apply)

    def close_without_apply(self):
        """Closes the window without applying changes to the main app."""
        self.grab_release()
        self.destroy()

    def update_hue_pointer(self, *args):
        self.hue_pointer_canvas.delete("ptr")
        val = self.hue_slider.get()
        
        # Actual track width calculation
        total_w = self.hue_pointer_canvas.winfo_width()
        if total_w <= 1: 
            # Fallback if window not yet rendered
            total_w = self.canvas_size
            
        # CTkSlider has some internal margins for the track (~10px each side)
        # We need to account for this to align the triangle with the handle.
        margin = 6 
        track_w = total_w - (2 * margin)
        handle_x = margin + (val * track_w)
        
        # Current Hue color
        r, g, b = colorsys.hsv_to_rgb(val, 1, 1)
        hex_c = "#{:02x}{:02x}{:02x}".format(int(r*255), int(g*255), int(b*255))
        
        # Draw ▼ Triangle
        points = [handle_x - 7, 0, handle_x + 7, 0, handle_x, 15]
        self.hue_pointer_canvas.create_polygon(points, fill=hex_c, outline="white", width=1, tags="ptr")

    def init_slots(self):
        for s in self.slots: s.destroy()
        self.slots = []
        
        mode = self.bit_mode.get()
        if mode == "2bit": 
            rows, cols = 4, 1
            max_slots = 4
        elif mode == "4bit": 
            rows, cols = 8, 2
            max_slots = 16
        else: return

        for r in range(rows):
            for c in range(cols):
                # Reduced size: 32x32 (~20% reduction from 40)
                # Reduced padding: 1.5 -> 1
                slot = ctk.CTkButton(self.slots_container, text="", width=32, height=32, border_width=2, 
                                      border_color="#444", fg_color="black", hover_color="#333")
                slot.grid(row=r, column=c, padx=1, pady=1)
                idx = len(self.slots)
                
                # Safety check
                if idx >= max_slots: 
                    slot.destroy()
                    continue

                # Map logical index: persistent_colors[idx]
                rgb = self.persistent_colors[idx]
                hex_c = "#{:02x}{:02x}{:02x}".format(*rgb)
                slot.configure(fg_color=hex_c, command=lambda i=idx: self.select_slot(i))
                self.slots.append(slot)
        
        # Keep selection valid if it was outside new range
        if self.current_slot_index >= len(self.slots):
            self.select_slot(0)
        else:
            self.select_slot(self.current_slot_index)

    def select_slot(self, index):
        self.current_slot_index = index
        for i, s in enumerate(self.slots):
            s.configure(border_color="#3498db" if i == index else "#444")

    def update_bit_ui(self):
        mode = self.bit_mode.get()
        if mode == "16bit":
            self.slot_frame.pack_forget()
            self.btn_add_color.configure(state="disabled")
        else:
            self.slot_frame.pack(pady=5, padx=20, fill="both", expand=True)
            self.btn_add_color.configure(state="normal")
            self.init_slots()

    def draw_sv_gradient(self):
        # High-performance gradient drawing using NumPy vectorization
        size = self.canvas_size
        import numpy as np
        
        # Create S and V grids
        s_coords = np.linspace(0, 1, size)
        v_coords = np.linspace(1, 0, size)
        s_grid, v_grid = np.meshgrid(s_coords, v_coords)
        
        h = self.current_h
        
        # HSV to RGB Conversion (Vectorized)
        i = (h * 6.0).astype(int) if isinstance(h, np.ndarray) else int(h * 6.0)
        f = (h * 6.0) - i
        p = v_grid * (1.0 - s_grid)
        q = v_grid * (1.0 - s_grid * f)
        t = v_grid * (1.0 - s_grid * (1.0 - f))
        i = i % 6
        
        rgb = np.zeros((size, size, 3))
        
        mask0 = (i == 0)
        mask1 = (i == 1)
        mask2 = (i == 2)
        mask3 = (i == 3)
        mask4 = (i == 4)
        mask5 = (i == 5)
        
        rgb[mask0] = np.stack([v_grid[mask0], t[mask0], p[mask0]], axis=-1)
        rgb[mask1] = np.stack([q[mask1], v_grid[mask1], p[mask1]], axis=-1)
        rgb[mask2] = np.stack([p[mask2], v_grid[mask2], t[mask2]], axis=-1)
        rgb[mask3] = np.stack([p[mask3], q[mask3], v_grid[mask3]], axis=-1)
        rgb[mask4] = np.stack([t[mask4], p[mask4], v_grid[mask4]], axis=-1)
        rgb[mask5] = np.stack([v_grid[mask5], p[mask5], q[mask5]], axis=-1)
        
        img_arr = (rgb * 255).astype(np.uint8)
        img = Image.fromarray(img_arr)
        
        self.tk_gradient = ImageTk.PhotoImage(img)
        self.sv_canvas.create_image(0, 0, anchor="nw", image=self.tk_gradient)

    def on_hue_change(self, val):
        self.current_h = float(val)
        # Update Hue Hex Label
        r, g, b = colorsys.hsv_to_rgb(self.current_h, 1, 1)
        hex_c = "#{:02x}{:02x}{:02x}".format(int(r*255), int(g*255), int(b*255))
        self.hue_hex_label.configure(text=f"Hue Hex: {hex_c.upper()}")
        
        self.update_hue_pointer()
        self.draw_sv_gradient()
        self.update_current_color()

    def on_sv_click(self, event):
        size = self.canvas_size
        self.current_s = max(0, min(1, event.x / size))
        self.current_v = max(0, min(1, 1 - (event.y / size)))
        self.update_current_color()

    def on_sv_hover(self, event):
        size = self.canvas_size
        s = max(0, min(1, event.x / size))
        v = max(0, min(1, 1 - (event.y / size)))
        r, g, b = colorsys.hsv_to_rgb(self.current_h, s, v)
        rgb = (int(r*255), int(g*255), int(b*255))
        hex_color = "#{:02x}{:02x}{:02x}".format(*rgb)
        self.cursor_hex_label.configure(text=f"Cursor: {hex_color.upper()}")

    def update_current_color(self):
        r, g, b = colorsys.hsv_to_rgb(self.current_h, self.current_s, self.current_v)
        rgb = (int(r*255), int(g*255), int(b*255))
        hex_color = "#{:02x}{:02x}{:02x}".format(*rgb)
        self.current_color_preview.configure(fg_color=hex_color)
        self.hex_label.configure(text=f"Current: {hex_color.upper()}")

    def add_current_color(self):
        r, g, b = colorsys.hsv_to_rgb(self.current_h, self.current_s, self.current_v)
        rgb = (int(r*255), int(g*255), int(b*255))
        hex_color = "#{:02x}{:02x}{:02x}".format(*rgb)
        
        # Update persistent storage
        self.persistent_colors[self.current_slot_index] = rgb
        self.slots[self.current_slot_index].configure(fg_color=hex_color)
        
        # Live Update
        if self.live_callback:
            self.live_callback(self.persistent_colors[:16])

        # Auto-advance
        if self.current_slot_index < len(self.slots) - 1:
            self.select_slot(self.current_slot_index + 1)

    def apply_to_main(self):
        mode = self.bit_mode.get()
        if mode == "16bit":
            self.current_callback("Custom_16bit", None)
        else:
            # Send exactly the number of colors for the current bit mode
            count = 4 if mode == "2bit" else 16
            self.current_callback("Custom_User", self.persistent_colors[:count])
        self.grab_release()
        self.destroy()

    def import_palette_file(self):
        # Temporarily release grab to allow system dialog to handle layout correctly
        self.grab_release()
        file_path = filedialog.askopenfilename(
            parent=self,
            title="Import Palette",
            filetypes=[("Palette Files", "*.gpl *.pal"), ("GIMP Palette", "*.gpl"), ("JASC Palette", "*.pal")]
        )
        # Restore grab after dialog is closed
        self.grab_set()
        
        if not file_path:
            return

        colors = []
        if file_path.lower().endswith('.gpl'):
            colors = PaletteParser.parse_gpl(file_path)
        elif file_path.lower().endswith('.pal'):
            colors = PaletteParser.parse_pal(file_path)

        if colors:
            self.apply_imported_colors(colors)

    def extract_palette_from_image(self):
        # Access parent's image path
        if hasattr(self.parent, 'original_image_path') and self.parent.original_image_path:
            try:
                img = Image.open(self.parent.original_image_path)
                mode = self.bit_mode.get()
                count = 4 if mode == "2bit" else 16
                colors = PaletteParser.extract_from_image(img, max_colors=count)
                if colors:
                    self.apply_imported_colors(colors)
            except Exception as e:
                print(f"Failed to extract colors: {e}")
        else:
             print("No image loaded in main app.")

    def apply_imported_colors(self, colors):
        # We need to fill up to 16 slots. If fewer colors, we pad with black or repeat? 
        # For now, just fill what we have, leave rest as is or black? 
        # Standard behavior: Overwrite from slot 0.
        
        for i, color in enumerate(colors):
            if i >= 16: break
            self.persistent_colors[i] = color
        
        # If the imported palette has fewer than 16 colors, maybe we should NOT clear the rest?
        # But if it's a "Palette Import", user expects exact match. 
        # Let's clear the remaining slots to black to avoid confusion.
        if len(colors) < 16:
            for i in range(len(colors), 16):
                self.persistent_colors[i] = (0, 0, 0)

        # Refresh UI
        self.init_slots()
        
        # Live Update
        if self.live_callback:
            self.live_callback(self.persistent_colors[:16])

class MagnifierWindow(ctk.CTkToplevel):
    """
    A separate window that shows a zoomed-in section of the preview image
    based on the cursor position.
    """
    def __init__(self, parent):
        super().__init__(parent)
        self.title("픽셀 돋보기 (Magnifier)")
        self.geometry("300x320")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.transient(parent)
        
        self.canvas_size = 300
        self.canvas = ctk.CTkCanvas(self, width=self.canvas_size, height=self.canvas_size, bg="#1a1a1a", highlightthickness=0)
        self.canvas.pack(pady=5)
        
        self.label_info = ctk.CTkLabel(self, text="이미지 위로 마우스를 가져가세요", font=("Arial", 11))
        self.label_info.pack()
        
        self.tk_img = None

    def update_zoom(self, image, center, zoom_level):
        """
        Updates the zoomed view of the image.
        image: PIL Image
        center: (x, y) coordinates in original image space
        zoom_level: int
        """
        if not image: return
        
        src_w, src_h = image.size
        # How much of the source image we want to see (depends on zoom)
        view_size = self.canvas_size // zoom_level
        
        cx, cy = center
        x0 = cx - view_size // 2
        y0 = cy - view_size // 2
        x1 = x0 + view_size
        y1 = y0 + view_size
        
        # Boundary checks
        crop_x0 = max(0, x0)
        crop_y0 = max(0, y0)
        crop_x1 = min(src_w, x1)
        crop_y1 = min(src_h, y1)
        
        crop = image.crop((crop_x0, crop_y0, crop_x1, crop_y1))
        
        # If crop is smaller than view_size (near edges), create a blank background
        final_crop = Image.new("RGBA", (view_size, view_size), (0,0,0,255))
        # Calculate paste position in the blank background
        paste_x = 0 if x0 >= 0 else abs(x0)
        paste_y = 0 if y0 >= 0 else abs(y0)
        final_crop.paste(crop, (paste_x, paste_y))
        
        # Scale up to canvas size
        zoomed = final_crop.resize((self.canvas_size, self.canvas_size), Image.NEAREST)
        
        self.tk_img = ImageTk.PhotoImage(zoomed)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.tk_img, anchor="nw")
        
        # Draw target crosshair
        mid = self.canvas_size // 2
        self.canvas.create_line(mid, mid-10, mid, mid+10, fill="red", width=1)
        self.canvas.create_line(mid-10, mid, mid+10, mid, fill="red", width=1)
        
        # Update label
        self.label_info.configure(text=f"Position: ({cx}, {cy}) | Zoom: x{zoom_level}")

class BatchExportWindow(ctk.CTkToplevel):
    def __init__(self, parent, start_callback):
        super().__init__(parent)
        self.title("일괄 저장 설정 (Batch Export Settings)")
        self.geometry("450x550")
        self.resizable(False, False)
        self.parent = parent
        self.start_callback = start_callback
        
        self.transient(parent)
        self.grab_set()

        # Layout
        ctk.CTkLabel(self, text="📦 일괄 저장 (Batch Export)", font=("Arial", 20, "bold")).pack(pady=20)

        # Formats Section
        format_frame = ctk.CTkFrame(self)
        format_frame.pack(pady=10, padx=20, fill="x")
        self.label_fmt = ctk.CTkLabel(format_frame, text="내보낼 포맷 선택:", font=("Arial", 12, "bold"))
        self.label_fmt.pack(pady=10, padx=10, anchor="w")
        self.parent.locale.register(self.label_fmt, "batch_formats")
        
        self.format_vars = {
            "PNG": ctk.BooleanVar(value=True),
            "JPG": ctk.BooleanVar(value=False),
            "BMP": ctk.BooleanVar(value=False),
            "WEBP": ctk.BooleanVar(value=False),
            "GIF": ctk.BooleanVar(value=False)
        }
        
        for fmt, var in self.format_vars.items():
            ctk.CTkCheckBox(format_frame, text=fmt, variable=var).pack(side="left", padx=10, pady=10)

        # Output Directory Section
        dir_frame = ctk.CTkFrame(self)
        dir_frame.pack(pady=10, padx=20, fill="x")
        self.label_path = ctk.CTkLabel(dir_frame, text="저장 경로:", font=("Arial", 12, "bold"))
        self.label_path.pack(pady=5, padx=10, anchor="w")
        self.parent.locale.register(self.label_path, "batch_path")
        
        self.entry_dir = ctk.CTkEntry(dir_frame)
        self.entry_dir.pack(side="left", fill="x", expand=True, padx=(10, 5), pady=10)
        
        self.btn_browse = ctk.CTkButton(dir_frame, text="찾기...", width=60, command=self.browse_dir)
        self.btn_browse.pack(side="right", padx=(0, 10), pady=10)

        # Advanced Options Section
        adv_frame = ctk.CTkFrame(self)
        adv_frame.pack(pady=10, padx=20, fill="x")
        self.var_spritesheet = ctk.BooleanVar(value=False)
        self.check_spritesheet = ctk.CTkCheckBox(adv_frame, text="스프라이트 시트 (Sprite Sheet)", variable=self.var_spritesheet)
        self.check_spritesheet.pack(pady=10, padx=10, anchor="w")
        self.parent.locale.register(self.check_spritesheet, "batch_spritesheet")

        self.var_separate = ctk.BooleanVar(value=False)
        self.check_separate = ctk.CTkCheckBox(adv_frame, text="레이어 분리 (Outline/Base)", variable=self.var_separate)
        self.check_separate.pack(pady=10, padx=10, anchor="w")
        self.parent.locale.register(self.check_separate, "batch_separate")

        # Progress Section
        self.progress_label = ctk.CTkLabel(self, text="준비됨", font=("Arial", 12))
        self.progress_label.pack(pady=(20, 5))
        
        self.progress_bar = ctk.CTkProgressBar(self, width=350)
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=10)

        # Log Area
        self.log_text = ctk.CTkTextbox(self, height=120, font=("Consolas", 10))
        self.log_text.pack(pady=10, padx=20, fill="x")

        # Action Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(side="bottom", pady=20, fill="x")
        
        self.btn_start = ctk.CTkButton(btn_frame, text="🚀 작업 시작", command=self.on_start, 
                                        fg_color="#2ecc71", hover_color="#27ae60", height=40, font=("Arial", 14, "bold"))
        self.btn_start.pack(side="left", padx=20, expand=True)
        
        self.btn_close = ctk.CTkButton(btn_frame, text="닫기", command=self.destroy, width=100)
        self.btn_close.pack(side="right", padx=20)

    def browse_dir(self):
        self.grab_release()
        d = filedialog.askdirectory(parent=self)
        self.grab_set()
        if d:
            self.entry_dir.delete(0, "end")
            self.entry_dir.insert(0, d)

    def on_start(self):
        output_dir = self.entry_dir.get()
        if not output_dir:
            self.log("❌ 오류: 저장 경로를 선택하세요.")
            return
            
        selected_formats = [fmt for fmt, var in self.format_vars.items() if var.get()]
        if not selected_formats and not self.var_spritesheet.get() and not self.var_separate.get():
            self.log("❌ 오류: 최소 하나의 포맷 또는 옵션을 선택하세요.")
            return

        self.btn_start.configure(state="disabled")
        self.start_callback(output_dir, selected_formats, self, self.var_spritesheet.get(), self.var_separate.get())

    def log(self, message):
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.update_idletasks()

    def update_progress(self, current, total):
        val = current / total
        self.progress_bar.set(val)
        self.progress_label.configure(text=f"진행 중: {current} / {total}")
        self.update_idletasks()

class PluginWindow(ctk.CTkToplevel):
    """
    A window to manage installed plugins (Enable/Disable).
    """
    def __init__(self, parent, plugin_engine, on_change_callback):
        super().__init__(parent)
        self.title("플러그인 관리 (Plugin Manager)")
        self.geometry("500x400")
        self.resizable(False, False)
        self.plugin_engine = plugin_engine
        self.on_change_callback = on_change_callback
        
        self.transient(parent)
        self.grab_set()

        ctk.CTkLabel(self, text="🔌 설치된 플러그인", font=("Arial", 20, "bold")).pack(pady=20)

        self.scroll_frame = ctk.CTkScrollableFrame(self, width=450, height=250)
        self.scroll_frame.pack(pady=10, padx=20, fill="both", expand=True)

        self.load_plugins()

    def load_plugins(self):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        plugins = self.plugin_engine.plugins
        if not plugins:
            ctk.CTkLabel(self.scroll_frame, text="설치된 플러그인이 없습니다.", font=("Arial", 12, "italic")).pack(pady=20)
            return

        for p_id, p_data in plugins.items():
            meta = p_data["metadata"]
            
            item_frame = ctk.CTkFrame(self.scroll_frame, fg_color="#2a2a2a", corner_radius=8)
            item_frame.pack(fill="x", pady=5, padx=5)
            
            info_frame = ctk.CTkFrame(item_frame, fg_color="transparent")
            info_frame.pack(side="left", padx=10, pady=10, fill="x", expand=True)
            
            ctk.CTkLabel(info_frame, text=f"{meta.get('name')} v{meta.get('version')}", 
                         font=("Arial", 14, "bold"), anchor="w").pack(fill="x")
            ctk.CTkLabel(info_frame, text=meta.get("description"), 
                         font=("Arial", 11), text_color="#aaa", anchor="w").pack(fill="x")
            
            # Switch to enable/disable
            switch_var = ctk.BooleanVar(value=p_data["enabled"])
            switch = ctk.CTkSwitch(item_frame, text="", variable=switch_var, 
                                   command=lambda id=p_id, var=switch_var: self.toggle_plugin(id, var))
            switch.pack(side="right", padx=15)

    def toggle_plugin(self, plugin_id, var):
        enabled = var.get()
        if plugin_id in self.plugin_engine.plugins:
            self.plugin_engine.plugins[plugin_id]["enabled"] = enabled
            print(f"Plugin {plugin_id} {'enabled' if enabled else 'disabled'}")
            if self.on_change_callback:
                self.on_change_callback()

