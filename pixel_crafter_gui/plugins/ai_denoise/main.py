class AIDenoisePlugin(BasePlugin):
    """
    Implements a tensor-based smoothing to reduce noise.
    Future versions can load pre-trained weights for deep-learning denoising.
    """
    def run(self, image: Image.Image, params: dict) -> Image.Image:
        mode = image.mode
        rgb_img = image.convert("RGB")
        img_np = np.array(rgb_img).astype(np.float32) / 255.0
        img_t = torch.from_numpy(img_np).permute(2, 0, 1).unsqueeze(0)

        # 5x5 Gaussian Kernel for noise reduction
        k_size = 5
        sigma = 1.5
        coords = torch.arange(k_size).float() - k_size // 2
        g = torch.exp(-(coords**2) / (2 * sigma**2))
        g = g / g.sum()
        k2d = g.view(-1, 1) @ g.view(1, -1)
        k2d = k2d.view(1, 1, k_size, k_size).repeat(3, 1, 1, 1)

        # Convolution
        smoothed = torch.nn.functional.conv2d(img_t, k2d, groups=3, padding=k_size//2)
        
        # Blend original and smoothed to preserve some texture
        alpha = 0.7 # 70% smoothed, 30% original
        final_t = alpha * smoothed + (1 - alpha) * img_t
        
        res_np = (torch.clamp(final_t, 0, 1).squeeze(0).permute(1, 2, 0).numpy() * 255).astype(np.uint8)
        res_img = Image.fromarray(res_np)
        
        if mode == "RGBA":
            res_img = res_img.convert("RGBA")
            res_img.putalpha(image.split()[-1])
            
        return res_img
