# prompt-image-lab

Static page (GitHub Pages) -> token proxy -> tunnel -> ComfyUI on the lab PC. Text-to-image, prompt-based image editing, 1/2/4 variants, download one/all.

Ideogram is API-only; this uses local open models (Flux.1 / Flux Kontext / Qwen-Image-Edit).

## Lab PC setup
1. Install ComfyUI, download model weights that fit the GPU.
2. Build two workflows and export each via "Save (API Format)":
   - `workflows/txt2img.json`: text-to-image, with a latent node exposing `batch_size`.
   - `workflows/edit.json`: LoadImage + instruction prompt (Flux Kontext or Qwen-Image-Edit).
3. Run ComfyUI on 127.0.0.1:8188, then the proxy:
   `TOKEN=<secret> ORIGIN=https://berlogabob.github.io uv run proxy/proxy.py`
4. Tunnel port 8189 (`cloudflared tunnel --url http://127.0.0.1:8189` or Tailscale Funnel).
5. Open the Pages URL, enter the tunnel URL and token under "Connection".

The tunnel URL and token live only in the browser's localStorage, never in this repo.
