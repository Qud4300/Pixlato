class UIDebugPlugin(BasePlugin):
    def run(self, image: Image.Image, params: dict) -> Image.Image:
        # Draw a simple red border to indicate the UI hook is working
        draw = ImageDraw.Draw(image)
        w, h = image.size
        draw.rectangle([0, 0, w-1, h-1], outline="red", width=2)
        return image
