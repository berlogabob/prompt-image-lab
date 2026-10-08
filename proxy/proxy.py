# /// script
# requires-python = ">=3.10"
# dependencies = ["aiohttp"]
# ///
"""Bearer-token reverse proxy in front of ComfyUI. Run: TOKEN=... ORIGIN=https://user.github.io uv run proxy.py"""
import os
import aiohttp
from aiohttp import web

TOKEN = os.environ["TOKEN"]
ORIGIN = os.environ["ORIGIN"]
COMFY = os.environ.get("COMFY", "http://127.0.0.1:8188")
CORS = {
    "Access-Control-Allow-Origin": ORIGIN,
    "Access-Control-Allow-Headers": "Authorization, Content-Type",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
}


async def handle(req: web.Request) -> web.Response:
    if req.method == "OPTIONS":
        return web.Response(headers=CORS)
    if req.headers.get("Authorization") != f"Bearer {TOKEN}":
        return web.Response(status=401, headers=CORS)
    async with aiohttp.ClientSession() as s:
        async with s.request(req.method, COMFY + req.path_qs, data=await req.read(),
                             headers={"Content-Type": req.content_type}) as r:
            return web.Response(status=r.status, body=await r.read(),
                                content_type=r.content_type, headers=CORS)


app = web.Application(client_max_size=64 * 2**20)
app.router.add_route("*", "/{tail:.*}", handle)
web.run_app(app, host="127.0.0.1", port=8189)
