# /// script
# requires-python = ">=3.10"
# dependencies = ["aiohttp"]
# ///
"""End-to-end check against a mock Unsloth: uv run test_flow.py"""
import asyncio, importlib.util, os, sys, tempfile
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

PNG = bytes.fromhex("89504e470d0a1a0a")


async def mock():
    app = web.Application()
    async def gen(r):
        assert r.headers["Authorization"] == "Bearer k"
        b = await r.json()
        return web.json_response({"images": [{"id": f"g{i}"} for i in range(b["batch_size"])]})
    async def file(r): return web.Response(body=PNG)
    app.add_routes([web.post("/api/inference/images/generate", gen),
                    web.get("/api/inference/images/gallery/{id}/file", file)])
    s = TestServer(app); await s.start_server(); return s


async def main():
    os.environ["DATA"] = tempfile.mkdtemp(); os.environ["UNSLOTH_KEY"] = "k"
    m = await mock(); os.environ["UNSLOTH_URL"] = f"http://127.0.0.1:{m.port}"
    spec = importlib.util.spec_from_file_location("server", "server.py"); S = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(S)
    for name, pw, lvl, adm in [("ana", "pw1", "novice", 0), ("boss", "pw2", "expert", 1)]:
        import hashlib, os as _o
        salt = _o.urandom(16); c = S.db()
        c.execute("insert into users(name,salt,hash,level,admin) values(?,?,?,?,?)", (name, salt, S.pw_hash(pw, salt), lvl, adm)); c.commit()
    async with TestClient(TestServer(S.make_app())) as c:
        assert (await c.get("/api/tasks")).status == 401
        assert (await c.post("/api/login", json={"name": "ana", "password": "bad"})).status == 401
        assert (await c.post("/api/login", json={"name": "ana", "password": "pw1"})).status == 200
        r = await c.post("/api/generate", json={"task": "gen-1", "prompt": "red bike", "n": 4})
        files = (await r.json())["files"]; assert len(files) == 4
        assert (await c.post("/api/generate", json={"task": "gen-1", "prompt": "x", "n": 3})).status == 400
        assert (await c.get("/img/" + files[0])).status == 200
        aid = (await r.json())["attempt"]
        assert (await c.post("/api/finish", json={"task": "gen-1", "picked": [aid, 2], "rating": 4})).status == 200
        assert (await c.get("/api/admin/stats")).status == 403
        await c.post("/api/login", json={"name": "boss", "password": "pw2"})
        st = await (await c.get("/api/admin/stats")).json()
        row = next(x for x in st["summary"] if x["user"] == "ana" and x["task"] == "gen-1")
        assert row["attempts"] == 1 and row["status"] == "done" and row["rating"] == 4 and row["level"] == "novice"
        assert st["prompts"][0]["prompt"] == "red bike"
        assert (await c.get("/img/" + files[0])).status == 200  # admin may view
    print("ok")

asyncio.run(main())
