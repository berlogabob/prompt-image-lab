# prompt-image-lab

Static page (GitHub Pages) -> tunnel -> ComfyUI on the lab PC. Text-to-image, prompt-based editing, 1/2/4 variants, download one/all. Users just open the page.

## Lab PC setup (once)
1. Install ComfyUI, download Flux Kontext / Qwen-Image-Edit weights that fit the GPU.
2. Export two workflows via "Save (API Format)" into `workflows/txt2img.json` and `workflows/edit.json` (latent node must expose `batch_size`).
3. Start: `python main.py --enable-cors-header https://berlogabob.github.io`
4. Expose it: `tailscale funnel 8188` (stable https URL). Put that URL in `config.js`, commit, push.

The tunnel URL is the only secret; keep it unguessable and rotate it if leaked.
