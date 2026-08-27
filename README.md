# alaciega

Blindfold chess against [Maia](https://maiachess.com/) (human-like engine levels 1100–1900). After you move, the app asks board-visualization questions so you can catch a lost mental image. There is no speech in this version. One owner, one instance: clone it, put in your own API token, run it.

## Demo

Screenshots / a GIF of new game → play → verification question → replay will land here after the English UI pass. Until then: start a game, type SAN moves, answer the checks, open a finished game from the list to replay.

## Architecture

```
Next.js PWA  ──HTTPS──►  FastAPI + python-chess + lc0/Maia
(Vercel, or        Bearer token injected by a server-side
 optional Docker)      proxy (never sent to the browser)
                              │
                              ├── SQLite (games)
                              └── Maia .pb.gz weights
```

The browser only talks to `/api/proxy/*` on the Next.js origin. FastAPI checks `Authorization: Bearer <API_TOKEN>` on every route except `GET /health`.

## Quickstart (Docker)

You need Docker Compose and a cloned copy of this repo.

```bash
git clone https://github.com/Pedrojonfg/alaciega.git
cd alaciega
cp .env.example .env                 # set API_TOKEN to a long random string
cp frontend/.env.example frontend/.env
# frontend/.env API_TOKEN must match .env
docker compose up --build
curl -s http://localhost:8000/health   # {"ok":true}
```

The first build compiles [lc0](https://github.com/LeelaChessZero/lc0) with the Eigen CPU backend (works on x86_64 and ARM64). That takes a while; later starts reuse the image. Maia weights download on first run into `./weights/` and are not rebuilt into the image.

Play UI in another terminal (recommended: Next locally, or Vercel):

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. The token stays in `frontend/.env` on the server; the browser never sees it.

SQLite lives in `./data/`, weights in `./weights/`. Recreating the container keeps both.

### Optional: TLS with Caddy

Uncomment the `caddy` service in `docker-compose.yml` and set `BACKEND=backend:8000`. The repo `Caddyfile` already reads `DOMAIN` and `BACKEND`.

### Optional: frontend container

Vercel is the default host for the PWA (free, no lc0). If you cannot use Vercel:

```bash
docker build -t alaciega-web frontend/
docker run --rm -p 3000:3000 --env-file frontend/.env alaciega-web
```

Point `API_URL` at the backend the container can reach (for example `http://host.docker.internal:8000`).

## Manual install (no Docker)

Use this on a VPS where you would rather compile lc0 yourself (typical on ARM64).

1. **lc0** with Eigen (no GPU libraries):

   ```bash
   git clone --recurse-submodules https://github.com/LeelaChessZero/lc0.git
   cd lc0
   meson setup build --buildtype=release \
     -Dblas=true -Dopenblas=false -Dmkl=false \
     -Dplain_cuda=false -Dcudnn=false -Dopencl=false -Ddx=false \
     -Dgtest=false -Dispc=false
   meson compile -C build
   # install build/lc0 somewhere on PATH, e.g. /usr/local/bin/lc0
   ```

2. **Maia weights** (idempotent script, or curl by hand):

   ```bash
   export MAIA_WEIGHTS_DIR=./maia_weights
   export MAIA_LEVELS=1100,1300,1500,1700,1900
   ./scripts/download_maia_weights.sh
   ```

3. **Python env** (venv or conda):

   ```bash
   python3 -m venv .venv
   . .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env   # set API_TOKEN, LC0_PATH, MAIA_WEIGHTS_DIR
   uvicorn backend.app:app --host 127.0.0.1 --port 8000
   ```

4. **systemd** (example unit; adjust user and paths):

   ```ini
   [Service]
   WorkingDirectory=/opt/alaciega
   EnvironmentFile=/opt/alaciega/.env
   ExecStart=/opt/alaciega/.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8000
   Restart=on-failure
   ```

5. **Caddy** reverse proxy: use the repo `Caddyfile`, set `DOMAIN` to your host, keep `BACKEND` at `localhost:8000`.

6. **Frontend:** deploy `frontend/` to Vercel with `API_URL` (backend origin) and `API_TOKEN` as **server** env vars, not `NEXT_PUBLIC_*`.

## Environment variables

### Backend (`.env.example`)

| Variable | Meaning | Example |
|---|---|---|
| `API_TOKEN` | Bearer token for the API | `changeme` |
| `LC0_PATH` | lc0 binary | `/usr/local/bin/lc0` |
| `MAIA_WEIGHTS_DIR` | Directory of `maia-*.pb.gz` | `maia_weights` |
| `MAIA_LEVELS` | Levels the start script downloads | `1100,1300,1500,1700,1900` |
| `DATABASE_PATH` | SQLite file | `games.db` |
| `MAX_ONGOING` | Simultaneous live games | `3` |
| `CORS_ORIGINS` | Allowed browser origins | `http://localhost:3000` |
| `PGN_SITE` | PGN `Site` header | `localhost` |
| `MAIA_TEMPERATURE` | Move sampling temperature | `0.2` |
| `MAIA_MULTIPV` | Candidate lines | `5` |
| `MAIA_SEARCH_NODES` | Nodes per Maia move | `12` |

Docker Compose forces `LC0_PATH`, `MAIA_WEIGHTS_DIR`, and `DATABASE_PATH` to the container paths (`/usr/local/bin/lc0`, `/app/weights`, `/app/data/alaciega.db`).

### Frontend (`frontend/.env.example`)

| Variable | Meaning | Example |
|---|---|---|
| `API_URL` | Backend origin (server-side proxy only) | `http://127.0.0.1:8000` |
| `API_TOKEN` | Same token as the backend (server-side only) | `changeme` |

Do not put the token in `NEXT_PUBLIC_*`. `GET /health` is public; every other API route returns 401 without the bearer token.

## Known limits

- One owner, one instance. There are no user accounts, quotas, or an admin panel.
- Anyone who has the token can play on that instance. Do not expose a public API unless you accept that.
- lc0 is CPU-only (Eigen) in the Docker image. Fine for a handful of simultaneous games (`MAX_ONGOING`), not a shared club server.

## License

[MIT](LICENSE)

## Publishing a clean history

Old commits may still contain machine paths. The public repo should be **one** commit. When you are ready (this replaces `origin/main`):

```bash
# .env must stay untracked
git status
rm -rf .git
git init
git add .
git commit -m "Initial public release"
git remote add origin https://github.com/Pedrojonfg/alaciega.git
git branch -M main
git push -u origin main --force
```

`--force` drops the remote history. Skip it if anyone else has a clone of the old commits; push to a new empty GitHub repo instead. Put the rotated `API_TOKEN` from your local `.env` on the VPS as well.
