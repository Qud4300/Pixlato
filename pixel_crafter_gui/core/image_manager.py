"""
Image Manager for handling multiple images in inventory.
Supports GIF frame extraction and batch processing.
"""
from PIL import Image, ImageSequence
import os

class ImageManager:
    MAX_IMAGES = 256
    
    def __init__(self):
        # Each entry: {"id": int, "path": str, "name": str, "pil_image": Image, "thumbnail": Image}
        self.images = []
        self._next_id = 0
    
    def add_image(self, path):
        """
        Adds an image to the inventory.
        If it's a GIF, extracts all frames as separate images.
        Returns list of added IDs.
        """
        if len(self.images) >= self.MAX_IMAGES:
            print(f"Inventory full. Max {self.MAX_IMAGES} images.")
            return []
        
        added_ids = []
        
        try:
            img = Image.open(path)
            filename = os.path.basename(path)
            name_base, ext = os.path.splitext(filename)
            
            # Check if it's an animated GIF
            if ext.lower() == '.gif' and hasattr(img, 'n_frames') and img.n_frames > 1:
                # Extract all frames
                for i, frame in enumerate(ImageSequence.Iterator(img)):
                    if len(self.images) >= self.MAX_IMAGES:
                        break
                    
                    frame_copy = frame.convert("RGBA")
                    entry = {
                        "id": self._next_id,
                        "path": path,
                        "name": f"{name_base}_{i}",
                        "pil_image": frame_copy,
                        "thumbnail": self._create_thumbnail(frame_copy),
                        "params": None # For Phase 19 individual settings
                    }
                    self.images.append(entry)
                    added_ids.append(self._next_id)
                    self._next_id += 1
            else:
                # Single image
                img_rgba = img.convert("RGBA")
                entry = {
                    "id": self._next_id,
                    "path": path,
                    "name": name_base,
                    "pil_image": img_rgba,
                    "thumbnail": self._create_thumbnail(img_rgba),
                    "params": None # For Phase 19 individual settings
                }
                self.images.append(entry)
                added_ids.append(self._next_id)
                self._next_id += 1
                
        except Exception as e:
            print(f"Error adding image: {e}")
            
        return added_ids
    
    def remove_image(self, image_id):
        """Removes an image by its ID."""
        self.images = [img for img in self.images if img["id"] != image_id]
    
    def get_image(self, image_id):
        """Gets an image entry by ID."""
        for img in self.images:
            if img["id"] == image_id:
                return img
        return None
    
    def get_all(self):
        """Returns all image entries."""
        return self.images
    
    def clear(self):
        """Clears all images."""
        self.images = []
        self._next_id = 0
    
    def count(self):
        return len(self.images)
    
    def _create_thumbnail(self, img, size=(64, 64)):
        """Creates a thumbnail for display in inventory."""
        thumb = img.copy()
        thumb.thumbnail(size, Image.LANCZOS)
        return thumb
