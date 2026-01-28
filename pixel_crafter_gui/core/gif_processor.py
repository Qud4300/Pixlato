from PIL import Image, ImageSequence
from core.processor import pixelate_image, add_outline
from core.palette import apply_palette_unified
import os

def process_gif(input_path, output_path, pixel_size, palette_name, custom_colors=16, dither=True, outline_enabled=False):
    try:
        # Open the original GIF
        img = Image.open(input_path)
        
        frames = []
        original_duration = img.info.get('duration', 100)
        original_loop = img.info.get('loop', 0)
        
        # Iterate over frames
        for frame in ImageSequence.Iterator(img):
            # 1. Convert to RGBA to preserve transparency for outlines
            frame_rgba = frame.convert("RGBA")
            
            # 2. Pixelate (Downsample)
            w, h = frame_rgba.size
            small_w = max(1, w // pixel_size)
            small_h = max(1, h // pixel_size)
            
            small_frame = frame_rgba.resize((small_w, small_h), resample=Image.BOX)
            
            # 3. Apply Palette (core.palette.apply_palette_unified handles RGBA)
            processed_small = apply_palette_unified(small_frame, palette_name, custom_colors, dither)
            
            # 4. Add Outline if requested
            if outline_enabled:
                processed_small = add_outline(processed_small)

            # 5. Upscale back to original size (Nearest Neighbor)
            processed_final = processed_small.resize((w, h), resample=Image.NEAREST)
            
            # 6. Convert to P mode for GIF optimization
            # We use fallback to 'RGB' then 'P' if needed, or just ADAPTIVE quantize
            # For GIFs with transparency, 'P' mode is necessary.
            final_frame = processed_final.convert("P", palette=Image.ADAPTIVE, colors=255)
            
            frames.append(final_frame)
            
        if frames:
            # Save as GIF
            frames[0].save(
                output_path,
                save_all=True,
                append_images=frames[1:],
                duration=original_duration,
                loop=original_loop,
                optimize=False # Optimization often breaks pixel art sharpness
            )
            return True, len(frames)
        
        return False, 0
            
    except Exception as e:
        print(f"Error processing GIF: {e}")
        return False, 0
