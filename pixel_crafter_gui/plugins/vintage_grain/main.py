import random
from PIL import Image

class VintageGrainPlugin(BasePlugin):
    def run(self, image: Image.Image, params: dict) -> Image.Image:
        """
        Adds random noise to each pixel.
        """
        if image.mode != "RGBA":
            image = image.convert("RGBA")
            
        width, height = image.size
        pixels = image.load()
        
        # Intensity of grain (can be adjusted by params if we add UI support later)
        intensity = 15 
        
        for y in range(height):
            for x in range(width):
                r, g, b, a = pixels[x, y]
                if a == 0: continue # Skip transparent
                
                noise = random.randint(-intensity, intensity)
                r = max(0, min(255, r + noise))
                g = max(0, min(255, g + noise))
                b = max(0, min(255, b + noise))
                
                pixels[x, y] = (r, g, b, a)
                
        return image
