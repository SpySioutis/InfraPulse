# InfraPulse Manual

## 1. Project overview

InfraPulse is a self-hosted infrastructure monitoring platform. A central
server (web UI + FastAPI API + PostgreSQL 17) collects metrics from
lightweight InfraPulse agents installed on Linux hosts, evaluates health and
alert rules, and presents dashboards, history charts and notifications.

The agent only collects the documented metric families (CPU, memory, disks,
network counters, system info). It cannot execute commands, move files or
control processes.

## 2. Prerequisites

- Docker Engine 24+ with Docker Compose v2 (`docker compose version` must work).
- 4 GB free RAM recommended; ~2 GB disk for images on first build.
- Ports `8092` (UI) and `8003` (API) free, or override via `.env`.
- One or more Linux hosts for the agent (the central server itself works for a trial).

Check:

```sh
docker --version
docker compose version
```

## 3. Required software

Only Docker + Compose run the central application. For local development you
additionally need Python 3.12+, `uv`, Node 22+ and npm (§13). The agent needs
Python 3.10+ and `uv` (or pip) on each monitored host.

## 4. Installation (central server)

```sh
git clone <repository-url> infrapulse
cd infrapulse
cp .env.example .env
```

Edit `.env` (§5), then start with `./start.sh` (or `.command` / `.bat`).

## 5. Environment configuration

Required on first boot:

| Variable | Meaning |
|---|---|
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | bootstrap admin (change after first login) |

Tuning knobs (centralized — no hardcoded thresholds in code):

| Variable | Default | Meaning |
|---|---|---|
| `METRIC_RETENTION_DAYS` | `30` | raw samples kept (auto-cleaned probabilistically on ingest) |
| `HEARTBEAT_GRACE_SECONDS` | `180` | heartbeat age that marks a server offline |
| `CPU_WARN_PCT` / `CPU_CRIT_PCT` | `75` / `90` | health thresholds |
| `MEM_WARN_PCT` / `MEM_CRIT_PCT` | `80` / `95` | health thresholds |
| `DISK_WARN_PCT` / `DISK_CRIT_PCT` | `80` / `95` | health thresholds |
| `JWT_SECRET` / `JWT_EXPIRY_MINUTES` | dev default / 720 | token signing |
| `BACKEND_PORT` / `FRONTEND_PORT` | `8003` / `8092` | published ports |
| `POSTGRES_USER` / `PASSWORD` / `DB` | `infrapulse` | DB credentials |

Never commit `.env` (see `.gitignore`).

## 6. Database initialization

PostgreSQL 17 with data in the `pgdata` volume. Schema comes from
`backend/migrations/0001_initial.sql`, applied on every backend boot
(`python -m app.migrate`, tracked in `schema_migrations`). Manual run:

```sh
docker compose exec backend python -m app.migrate
```

## 7. Docker setup

| Service | Image / build | Ports | Health |
|---|---|---|---|
| `db` | `postgres:17`, volume `pgdata` | internal 5432 | `pg_isready` |
| `backend` | `Dockerfile` (uv + FastAPI) | `${BACKEND_PORT:-8003}:8000` | `GET /api/health` |
| `frontend` | `frontend/Dockerfile` (nginx + SPA) | `${FRONTEND_PORT:-8092}:80` | depends on backend |

## 8. Automatic startup

- Linux: `./start.sh`
- macOS: `./start.command` (double-click works too)
- Windows: `start.bat`

Each script checks Docker/Compose, then runs `docker compose up --build`.
A missing `.env` (or missing `ADMIN_*`) stops Compose with a clear message.

After startup: UI http://localhost:8092 · API docs http://localhost:8003/api/docs.
Log in with your `ADMIN_USERNAME` / `ADMIN_PASSWORD`.

## 9. Manual startup

```sh
cd /path/to/infrapulse
docker compose up --build        # foreground; Ctrl-C stops
docker compose up --build -d     # detached
```

## 10. How to stop

- Foreground: `Ctrl-C`. Detached: `docker compose down` (keeps `pgdata`).
- Full reset including all metrics: `docker compose down -v`.

## 11. Agent installation (monitored Linux hosts)

1. **Create a server entry** in the UI (Servers → Register server) or API:
   ```sh
   curl -s -X POST http://SERVER:8003/api/servers \
     -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
     -d '{"name":"web-prod-1","hostname":"web1.example.com","environment":"production"}'
   ```
2. **Generate a registration token** (Servers → server details → Generate
   registration token, or `POST /api/servers/{id}/registration-token`).
   It is single-use, expires in 24h, and is shown once — copy it now.
3. **Install the agent** on the monitored host:
   ```sh
   git clone <repository-url> infrapulse && cd infrapulse/agent
   uv sync   # or: pip install -e .   (needs Python 3.10+ and psutil)
   ```
4. **Configure** `/etc/infrapulse/agent.json` (mode 0600):
   ```json
   {
     "server_url": "http://CENTRAL:8003",
     "registration_token": "PASTE_SINGLE_USE_TOKEN_HERE",
     "interval_seconds": 60
   }
   ```
   (`AGENT_CONFIG` env overrides the path; `SERVER_URL`, `REGISTRATION_TOKEN`,
   `AGENT_INTERVAL_SECONDS` env vars override file values.)
5. **Register**: `uv run python -m infrapulse_agent --once` prints one report
   (dry run, no registration). A normal start exchanges the token for a
   persistent agent credential and deletes the registration token from config.
6. **Run**: `uv run python -m infrapulse_agent`
7. **systemd** (recommended): copy `agent/systemd/infrapulse-agent.service`,
   adjust `ExecStart`/`Environment` paths, then:
   ```sh
   sudo useradd -r -s /usr/sbin/nologin infrapulse
   sudo mkdir -p /etc/infrapulse && sudo cp agent.json /etc/infrapulse/
   sudo cp infrapulse-agent.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now infrapulse-agent
   ```
8. **Logs**: `journalctl -u infrapulse-agent -f` (or stdout when run manually).
9. **Troubleshooting**: connection refused → check `server_url` and firewall;
   401 → token used/expired/revoked → generate a fresh registration token;
   no data in UI → agent logs + `last_heartbeat_at` on the Agents page.
10. **Revoke**: Agents page → Revoke (admin). The agent stops being accepted
    immediately; register again with a fresh token to resume.

## 12. How to run tests

Backend (12 tests: health rules, auth, servers/groups, agent lifecycle,
ingestion incl. throughput, offline detection, alert dedup/resolution,
retention config — mocked DB via SQLite, no real agents):

```sh
cd backend
uv sync
uv run pytest -q
```

Agent (6 tests: collector shape, error resilience, config precedence,
registration validation):

```sh
cd agent
uv sync
uv run pytest -q
```

Frontend (7 vitest tests: health helpers, formatting, API params):

```sh
cd frontend
npm install
npm test
npm run build   # also typechecks (vue-tsc) and produces dist/
```

Full-stack validation: `docker compose up --build -d`, register a server,
run the agent with `AGENT_INTERVAL_SECONDS=10`, watch the dashboard.

## 13. Development workflow

- Backend without Docker: `cd backend && uv sync && uv run uvicorn app.main:app --reload`
  (needs local Postgres + `DATABASE_URL` + `ADMIN_*` env).
- Frontend without Docker: `cd frontend && npm install && npm run dev`
  (Vite proxies `/api` → `http://localhost:8003`).
- Agent locally: `cd agent && uv sync && AGENT_CONFIG=/tmp/agent.json uv run python -m infrapulse_agent`
- Manual full evaluation: `POST /api/alerts/evaluate` (the UI Alerts page has
  an Evaluate now button; wire it to cron/systemd for scheduled sweeps).
- Keep `MANUAL.md`, `AGENTS.md`, `README.md`, `.env.example` in sync.

## 14. Backup and restoration

```sh
docker compose exec db pg_dump -U infrapulse infrapulse > infrapulse-backup.sql
cat infrapulse-backup.sql | docker compose exec -T db psql -U infrapulse -d infrapulse
```

Metric samples dominate size; retention cleanup keeps growth bounded.

## 15. Screenshots

Screenshots in `docs/screenshots/` are real captures of the running app with a
live agent reporting (plus one offline demo server). Captured with headless
Chromium driven over CDP against the running stack (token injected into
localStorage, pages captured one by one; the terminal/license equivalents do
not apply here — see README for the file list).

## 16. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Compose errors about `ADMIN_USERNAME` | No `.env`: `cp .env.example .env` and set credentials. |
| Backend exits: admin bootstrap | Same as above — required once on an empty DB. |
| `401` on API calls | Token expired/invalid: log in again; check `JWT_SECRET` stability. |
| Agent `401 invalid or revoked` | Re-register: generate a fresh token (single-use). Used tokens never work twice. |
| Agent `cannot reach server` | Wrong `server_url`, firewall, or central stack down. |
| Server stuck `unknown` | Agent never reported: check agent logs + Agents page heartbeat. |
| Server `offline` | No heartbeat within grace period: agent stopped, host down, or network cut. |
| False `offline` flapping | Interval longer than grace (e.g. 60s interval with heavy jitter): raise `HEARTBEAT_GRACE_SECONDS` to ~3-4× the interval. |
| Disk growth | Lower `METRIC_RETENTION_DAYS`; cleanup runs probabilistically on ingest. |
| Blank dashboard | No data yet — register a server + run the agent (§11). |
| Frontend `Could not load…` | Backend unreachable: `curl http://localhost:8003/api/health`; `docker compose ps`. |

## 17. Security notes

- Change the bootstrap admin password; create per-operator accounts (admin panel in Settings).
- Agent tokens are bearer credentials: shown once, hashed at rest, revokable. Re-register rather than sharing tokens between hosts.
- Agents authenticate with tokens only — never with user passwords — and can only submit their own server's data.
- All input validated server-side; SQLAlchemy parameter binding throughout; no secrets in logs or error bodies (tests assert this for error mapping).
- Rate limiting is in-memory and the registry/session state is per-process: run a single backend replica.
- Expose the stack to monitored networks only; terminate TLS in front (reverse proxy) for internet-facing deployments.
