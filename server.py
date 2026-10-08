# /// script
# requires-python = ">=3.10"
# dependencies = ["aiohttp"]
# ///
"""Study server: logins, task cards, prompt logging, Unsloth Studio proxy, admin stats.

  uv run server.py adduser NAME PASSWORD LEVEL [--admin]   (re-running resets the password)
  UNSLOTH_KEY=... uv run server.py                          (serves on 127.0.0.1:8080)
"""
import asyncio, base64, csv, hashlib, hmac, io, json, os, secrets, sqlite3, sys, time
from pathlib import Path
from aiohttp import ClientSession, ClientTimeout, web

ROOT = Path(__file__).parent
DATA = Path(os.environ.get("DATA", ROOT / "data"))
UNSLOTH = os.environ.get("UNSLOTH_URL", "http://127.0.0.1:8888")
KEY = os.environ.get("UNSLOTH_KEY", "")
VARIANTS = (1, 2, 4)
SCHEMA = """
create table if not exists users(id integer primary key, name text unique, salt blob, hash blob,
  level text, admin integer default 0);
create table if not exists attempts(id integer primary key, user_id int, task text, prompt text,
  n int, files text, ts real, secs real);
create table if not exists results(user_id int, task text, attempt_id int, picked int, rating int,
  ts real, primary key(user_id, task));
"""


def db():
    DATA.mkdir(exist_ok=True)
    c = sqlite3.connect(DATA / "study.db")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c


def pw_hash(pw, salt):
    return hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1)


def secret():
    f = DATA / ".secret"
    DATA.mkdir(exist_ok=True)
    if not f.exists():
        f.write_text(secrets.token_hex(32))
    return f.read_text().encode()


def sign(uid):
    body = f"{uid}.{int(time.time()) + 7 * 86400}"
    return body + "." + hmac.new(secret(), body.encode(), "sha256").hexdigest()


def verify(cookie):
    try:
        uid, exp, mac = cookie.split(".")
        good = hmac.new(secret(), f"{uid}.{exp}".encode(), "sha256").hexdigest()
        return int(uid) if hmac.compare_digest(mac, good) and int(exp) > time.time() else None
    except Exception:
        return None


def tasks():
    return json.loads((ROOT / "tasks" / "tasks.json").read_text())


def user_of(req):
    uid = verify(req.cookies.get("s", ""))
    u = db().execute("select * from users where id=?", (uid,)).fetchone() if uid else None
    if not u:
        raise web.HTTPUnauthorized()
    return u


def admin_of(req):
    u = user_of(req)
    if not u["admin"]:
        raise web.HTTPForbidden()
    return u


fails = {}  # ponytail: in-memory login throttle, resets on restart


async def login(req):
    b = await req.json()
    name = str(b.get("name", ""))
    f = [t for t in fails.get(name, []) if t > time.time() - 60]
    if len(f) >= 5:
        raise web.HTTPTooManyRequests()
    u = db().execute("select * from users where name=?", (name,)).fetchone()
    ok = u and hmac.compare_digest(pw_hash(str(b.get("password", "")), u["salt"]), u["hash"])
    if not ok:
        fails[name] = f + [time.time()]
        raise web.HTTPUnauthorized()
    r = web.json_response({"name": name, "admin": bool(u["admin"])})
    r.set_cookie("s", sign(u["id"]), httponly=True, samesite="None" if ORIGIN else "Lax", max_age=7 * 86400,
                 secure=bool(ORIGIN) or req.headers.get("X-Forwarded-Proto") == "https")
    return r


async def logout(req):
    r = web.json_response({})
    r.del_cookie("s")
    return r


async def me(req):
    u = user_of(req)
    return web.json_response({"name": u["name"], "admin": bool(u["admin"])})


async def task_list(req):
    u = user_of(req)
    c = db()
    out = []
    for t in tasks():
        n = c.execute("select count(*) from attempts where user_id=? and task=?", (u["id"], t["id"])).fetchone()[0]
        r = c.execute("select picked, rating from results where user_id=? and task=?", (u["id"], t["id"])).fetchone()
        hist = [dict(prompt=a["prompt"], n=a["n"], files=json.loads(a["files"]), id=a["id"]) for a in
                c.execute("select * from attempts where user_id=? and task=? order by id", (u["id"], t["id"]))]
        out.append({**t, "attempts": n, "done": bool(r), "rating": r and r["rating"], "history": hist})
    return web.json_response(out)


async def generate(req):
    u = user_of(req)
    b = await req.json()
    t = next((t for t in tasks() if t["id"] == b.get("task")), None)
    prompt, n = str(b.get("prompt", "")).strip(), b.get("n")
    if not t or not prompt or len(prompt) > 2000 or n not in VARIANTS:
        raise web.HTTPBadRequest()
    body = {"prompt": prompt, "batch_size": n, "width": 1024, "height": 1024}
    if t["kind"] == "edit":
        img = (ROOT / "tasks" / t["image"]).read_bytes()
        body |= {"init_image": "data:image/png;base64," + base64.b64encode(img).decode(), "strength": 0.7}
        if os.environ.get("EDIT_WORKFLOW"):
            body["workflow"] = os.environ["EDIT_WORKFLOW"]
    h = {"Authorization": f"Bearer {KEY}"}
    t0 = time.time()
    async with req.app["gpu"], ClientSession(timeout=ClientTimeout(total=900)) as s:  # one GPU job at a time
        async with s.post(f"{UNSLOTH}/api/inference/images/generate", json=body, headers=h) as r:
            if r.status != 200:
                raise web.HTTPBadGateway(text=await r.text())
            recs = (await r.json())["images"]
        blobs = []
        for rec in recs:
            async with s.get(f"{UNSLOTH}/api/inference/images/gallery/{rec['id']}/file", headers=h) as r:
                blobs.append(await r.read())
    c = db()
    cur = c.execute("insert into attempts(user_id,task,prompt,n,files,ts,secs) values(?,?,?,?,?,?,?)",
                    (u["id"], t["id"], prompt, n, "[]", time.time(), time.time() - t0))
    aid = cur.lastrowid
    (DATA / "img").mkdir(exist_ok=True)
    files = []
    for i, blob in enumerate(blobs):
        (DATA / "img" / f"{aid}_{i}.png").write_bytes(blob)
        files.append(f"{aid}_{i}.png")
    c.execute("update attempts set files=? where id=?", (json.dumps(files), aid))
    c.commit()
    return web.json_response({"attempt": aid, "files": files})


async def finish(req):
    u = user_of(req)
    b = await req.json()
    c = db()
    picked = b.get("picked")  # [attempt_id, index] or null = gave up
    rating = b.get("rating")
    if picked is not None:
        a = c.execute("select * from attempts where id=? and user_id=? and task=?",
                      (picked[0], u["id"], b.get("task"))).fetchone()
        if not a or rating not in (1, 2, 3, 4, 5) or not 0 <= picked[1] < a["n"]:
            raise web.HTTPBadRequest()
    c.execute("insert or replace into results values(?,?,?,?,?,?)",
              (u["id"], b["task"], picked and picked[0], picked and picked[1], picked and rating, time.time()))
    c.commit()
    return web.json_response({})


async def image(req):
    u = user_of(req)
    name = Path(req.match_info["name"]).name
    a = db().execute("select user_id from attempts where id=?", (name.split("_")[0],)).fetchone()
    if not a or (a["user_id"] != u["id"] and not u["admin"]):
        raise web.HTTPNotFound()
    return web.FileResponse(DATA / "img" / name)


async def task_image(req):
    user_of(req)
    return web.FileResponse(ROOT / "tasks" / Path(req.match_info["name"]).name)


def stats_rows():
    c = db()
    rows = []
    for u in c.execute("select * from users where admin=0 order by name"):
        for t in tasks():
            a = c.execute("select count(*) n, coalesce(sum(n),0) imgs, coalesce(avg(length(prompt)),0) plen, "
                          "min(ts) t0 from attempts where user_id=? and task=?", (u["id"], t["id"])).fetchone()
            r = c.execute("select * from results where user_id=? and task=?", (u["id"], t["id"])).fetchone()
            rows.append({"user": u["name"], "level": u["level"], "task": t["id"], "attempts": a["n"],
                         "images": a["imgs"], "avg_prompt_chars": round(a["plen"]),
                         "status": "gave_up" if r and r["picked"] is None else "done" if r else
                         "in_progress" if a["n"] else "not_started",
                         "rating": r["rating"] if r else None,
                         "minutes": round((r["ts"] - a["t0"]) / 60, 1) if r and a["t0"] else None})
    return rows


async def admin_stats(req):
    admin_of(req)
    c = db()
    prompts = [dict(r) for r in c.execute(
        "select a.id, u.name user, u.level, a.task, a.prompt, a.n, a.files, a.ts from attempts a "
        "join users u on u.id=a.user_id order by a.id")]
    return web.json_response({"summary": stats_rows(), "prompts": prompts})


async def admin_csv(req):
    admin_of(req)
    rows = stats_rows()
    out = io.StringIO()
    if rows:
        w = csv.DictWriter(out, rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    return web.Response(text=out.getvalue(), content_type="text/csv",
                        headers={"Content-Disposition": "attachment; filename=summary.csv"})


ORIGIN = os.environ.get("ORIGIN", "")  # e.g. https://berlogabob.github.io when the UI is hosted on Pages


@web.middleware
async def cors(req, handler):
    try:
        resp = web.Response() if req.method == "OPTIONS" else await handler(req)
    except web.HTTPException as e:
        resp = e
    if ORIGIN:
        resp.headers.update({"Access-Control-Allow-Origin": ORIGIN, "Access-Control-Allow-Credentials": "true",
                             "Access-Control-Allow-Headers": "Content-Type", "Vary": "Origin"})
    return resp


def make_app():
    app = web.Application(client_max_size=1 << 20, middlewares=[cors])
    app["gpu"] = asyncio.Lock()
    app.add_routes([
        web.post("/api/login", login), web.post("/api/logout", logout), web.get("/api/me", me),
        web.get("/api/tasks", task_list), web.post("/api/generate", generate), web.post("/api/finish", finish),
        web.get("/img/{name}", image), web.get("/task-img/{name}", task_image),
        web.get("/api/admin/stats", admin_stats), web.get("/api/admin/summary.csv", admin_csv),
        web.get("/", lambda r: web.FileResponse(ROOT / "index.html")),
        web.get("/admin", lambda r: web.FileResponse(ROOT / "admin.html")),
        web.get("/config.js", lambda r: web.FileResponse(ROOT / "config.js")),
    ])
    return app


if __name__ == "__main__":
    if sys.argv[1:2] == ["adduser"]:
        name, pw, level = sys.argv[2:5]
        salt, c = os.urandom(16), db()
        c.execute("insert into users(name,salt,hash,level,admin) values(?,?,?,?,?) on conflict(name) do update "
                  "set salt=excluded.salt, hash=excluded.hash, level=excluded.level, admin=excluded.admin",
                  (name, salt, pw_hash(pw, salt), level, int("--admin" in sys.argv)))
        c.commit()
        print("ok")
    else:
        web.run_app(make_app(), host="127.0.0.1", port=int(os.environ.get("PORT", 8080)))
