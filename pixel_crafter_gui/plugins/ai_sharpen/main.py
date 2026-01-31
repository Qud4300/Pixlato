class AISharpenPlugin(BasePlugin):
    def run(self, image: Image.Image, params: dict) -> Image.Image:
        # Convert PIL to Torch Tensor (C, H, W)
        # We process RGB to avoid issues with Alpha in convolution
        mode = image.mode
        rgb_img = image.convert("RGB")
        img_np = np.array(rgb_img).astype(np.float32) / 255.0
        img_t = torch.from_numpy(img_np).permute(2, 0, 1).unsqueeze(0) # (1, 3, H, W)

        # Define Sharpening Kernel
        # Center is 5, neighbors are -1. Sum is 1.
        kernel = torch.tensor([
            [ 0, -1,  0],
            [-1,  5, -1],
            [ 0, -1,  0]
        ], dtype=torch.float32).view(1, 1, 3, 3).repeat(3, 1, 1, 1)

        # Apply convolution with groups=3 for independent RGB channels
        sharpened = torch.nn.functional.conv2d(img_t, kernel, groups=3, padding=1)
        
        # Clamp values to [0, 1] to prevent artifacts
        sharpened = torch.clamp(sharpened, 0.0, 1.0)
        
        # Convert back to PIL
        res_np = (sharpened.squeeze(0).permute(1, 2, 0).numpy() * 255).astype(np.uint8)
        res_img = Image.fromarray(res_np)
        
        # Restore alpha if original had it
        if mode == "RGBA":
            res_img = res_img.convert("RGBA")
            res_img.putalpha(image.split()[-1])
            
        return res_img
