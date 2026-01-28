import os
from PIL import Image

class PaletteParser:
    @staticmethod
    def parse_gpl(file_path):
        """
        Parses a GIMP Palette (.gpl) file.
        Returns a list of (R, G, B) tuples.
        """
        colors = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
                # Check header
                if not lines or "GIMP Palette" not in lines[0]:
                    print(f"Invalid GPL file: {file_path}")
                    return []

                for line in lines:
                    line = line.strip()
                    if not line or line.startswith('#') or line.startswith("GIMP Palette") or line.startswith("Name:"):
                        continue
                    
                    # GPL format: R G B Name
                    parts = line.split()
                    if len(parts) >= 3:
                        try:
                            # It's possible for parts to be just R G B, or R G B Name
                            r = int(parts[0])
                            g = int(parts[1])
                            b = int(parts[2])
                            colors.append((r, g, b))
                        except ValueError:
                            continue
        except Exception as e:
            print(f"Error parsing GPL: {e}")
            return []
            
        return colors

    @staticmethod
    def parse_pal(file_path):
        """
        Parses a JASC Palette (.pal) file.
        Returns a list of (R, G, B) tuples.
        """
        colors = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
                # Check header "JASC-PAL"
                if not lines or "JASC-PAL" not in lines[0]:
                    print(f"Invalid PAL file: {file_path}")
                    return []

                # Line 2 is version (0100), Line 3 is number of colors.
                # Actual colors start from line 4
                start_index = 3 
                
                for i in range(start_index, len(lines)):
                    line = lines[i].strip()
                    if not line:
                        continue
                        
                    parts = line.split()
                    if len(parts) >= 3:
                        try:
                            # PAL format: R G B
                            r = int(parts[0])
                            g = int(parts[1])
                            b = int(parts[2])
                            colors.append((r, g, b))
                        except ValueError:
                            continue
        except Exception as e:
            print(f"Error parsing PAL: {e}")
            return []
            
        return colors

    @staticmethod
    def extract_from_image(image: Image.Image, max_colors=16):
        """
        Extracts dominant colors from a PIL Image.
        Returns a list of (R, G, B) tuples.
        """
        if not image:
            return []
            
        try:
            # Convert to RGB and resize to speed up processing
            img_rgb = image.convert("RGB")
            img_rgb.thumbnail((256, 256))
            
            # Use Adaptive palette conversion for dominant colors
            # This is more representative for pixel art than simple quantization
            p_img = img_rgb.convert("P", palette=Image.Palette.ADAPTIVE, colors=max_colors)
            
            # Get the raw palette data
            raw_pal = p_img.getpalette()
            
            # Extract unique RGB tuples (getpalette returns 768 entries usually)
            colors = []
            seen = set()
            for i in range(max_colors):
                r = raw_pal[i*3]
                g = raw_pal[i*3+1]
                b = raw_pal[i*3+2]
                col = (r, g, b)
                if col not in seen:
                    colors.append(col)
                    seen.add(col)
            
            return colors

        except Exception as e:
            print(f"Error extracting colors: {e}")
            return []
