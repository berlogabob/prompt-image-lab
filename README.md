# prompt-image-lab

Research tool: participants with different expertise solve the same flash-card tasks (generate / edit an image) by prompting; we log every prompt and attempt and the participant's own verdict on the result.

One Python server on the studio PC does everything: logins, task cards, prompt logging, admin stats, and proxies image jobs to Unsloth Studio (its API key never reaches the browser). Expose it through one tunnel. The UI is either served by the server itself (tunnel URL) or hosted on GitHub Pages (https://berlogabob.github.io/prompt-image-lab/), which calls the server cross-origin.

## Run (studio PC)
1. Unsloth Studio running with an image model loaded; create an API key in Studio.
2. Accounts: copy `users.example.toml` to `users.toml` (gitignored, plain text: password, level, admin). Edits apply immediately; no recovery flow, you assign passwords.
3. Tasks: edit `tasks/tasks.json` (`kind` generate|edit; edit tasks need `image` = file in `tasks/`; generate tasks may show a reference `image`).
4. `UNSLOTH_KEY=... uv run server.py` then `tailscale funnel 8080` (or `cloudflared tunnel --url http://127.0.0.1:8080`). Share the URL + logins.
   For the Pages UI: set `ORIGIN=https://berlogabob.github.io` when starting the server, and put the tunnel URL in `BASE` in `config.js` (commit, push). Needs HTTPS tunnel; browsers that block third-party cookies will break login, then use the tunnel URL directly.
   Optional env: `UNSLOTH_URL` (default http://127.0.0.1:8888), `EDIT_WORKFLOW` (Studio edit workflow name), `PORT`, `DATA`.

## Data
`data/study.db` (SQLite: users, attempts, results) and `data/img/` (all generated images). `/admin` (admin accounts only) shows per-user/task attempts, images, prompt length, minutes, rating, status, plus full prompt history with thumbnails; summary CSV download.

Flow per task: write prompt, pick 1/2/4 variants, iterate; participant picks the image they consider good, rates it 1-5, or gives up. Attempts count = prompts submitted.

`uv run test_flow.py` runs an end-to-end check against a mock Unsloth.

## Status (2026-10-09)
Code complete and tested against a mock Unsloth only. Not yet deployed.

Next steps
1. Studio PC (`desktop-vdsrh2e` on the tailnet; Unsloth Studio on :8888, SSH/other ports blocked by Windows firewall): clone repo, create `users.toml`, create Studio API key, load an image model.
2. Run server with `ORIGIN=https://berlogabob.github.io`, open HTTPS tunnel (`tailscale funnel 8080`), put the URL in `config.js` `BASE`, push.
3. Real-model checks: txt2img, edit (`init_image`, maybe `EDIT_WORKFLOW`), 1/2/4 variants, `/admin` stats.
4. Replace sample tasks in `tasks/tasks.json`.

Known limits: one GPU job at a time; Cloudflare Tunnel ~100 s request cap (Tailscale Funnel has none); edits always restart from the source image; only the participant's own 1-5 rating (no separate boss rating); third-party-cookie blocking (e.g. Brave) breaks login on the github.io UI, use the tunnel URL directly.
