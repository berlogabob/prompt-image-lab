# prompt-image-lab

Research tool: participants with different expertise solve the same flash-card tasks (generate / edit an image) by prompting; we log every prompt and attempt and the participant's own verdict on the result.

One Python server on the studio PC does everything: logins, task cards, prompt logging, admin stats, and proxies image jobs to Unsloth Studio (its API key never reaches the browser). Expose it through one tunnel; no GitHub Pages needed.

## Run (studio PC)
1. Unsloth Studio running with an image model loaded; create an API key in Studio.
2. Accounts (no password recovery; re-running resets the password):
   `uv run server.py adduser ana pw123 novice` / `... adduser boss pw456 expert --admin`
   Level is a free label (novice/intermediate/expert) used to group the stats.
3. Tasks: edit `tasks/tasks.json` (`kind` generate|edit; edit tasks need `image` = file in `tasks/`; generate tasks may show a reference `image`).
4. `UNSLOTH_KEY=... uv run server.py` then `tailscale funnel 8080` (or `cloudflared tunnel --url http://127.0.0.1:8080`). Share the URL + logins.
   Optional env: `UNSLOTH_URL` (default http://127.0.0.1:8888), `EDIT_WORKFLOW` (Studio edit workflow name), `PORT`, `DATA`.

## Data
`data/study.db` (SQLite: users, attempts, results) and `data/img/` (all generated images). `/admin` (admin accounts only) shows per-user/task attempts, images, prompt length, minutes, rating, status, plus full prompt history with thumbnails; summary CSV download.

Flow per task: write prompt, pick 1/2/4 variants, iterate; participant picks the image they consider good, rates it 1-5, or gives up. Attempts count = prompts submitted.

`uv run test_flow.py` runs an end-to-end check against a mock Unsloth.
