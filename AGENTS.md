# AGENTS.md — InfraPulse contributor guide for AI coding agents

## Architecture

Three Docker Compose services (`compose.yaml` at repo root):

- `db` — PostgreSQL 17, persistent `pgdata` volume, `pg_isready` healthcheck.
- `backend` — built from root `Dockerfile` (uv + FastAPI on :8000, published
  as `${BACKEND_PORT:-8003}`). On boot: SQL migrations (`python -m app.migrate`)
  + admin bootstrap (fails fast without `ADMIN_*` on an empty DB), then uvicorn.
  Health: `GET /api/health`.
- `frontend` — built from `frontend/Dockerfile` (node build → nginx on :80,
  `/api/` → `backend:8000`, SPA fallback).

Plus the out-of-compose **agent** (`agent/`, Python + psutil + stdlib HTTP):
runs on monitored hosts, reports every `interval_seconds` (default 60).

No background workers/schedulers in the backend: alert evaluation runs on
metric ingest (per-server rules + offline resolution) plus explicit
`POST /api/alerts/evaluate` (for cron/systemd). Retention cleanup is
probabilistic inside ingest (`maybe_retain`, 5% of reports).

## Directory structure

```text
backend/
  app/
    main.py            # FastAPI app, lifespan (admin bootstrap), router wiring under /api
    config.py          # centralized thresholds/retention/grace (env-overridable)
    database.py        # engine + SessionLocal + get_db
    models.py          # User, ServerGroup, Server, Agent, RegistrationToken,
                       # MetricSample, AlertRule, Alert, Notification, AuditEvent
    schemas.py         # Pydantic models; agent payload schemas validate untrusted input
    health.py          # pure health evaluation (status + reasons)
    alerting.py        # rule evaluation, dedup/cooldown, offline incidents, resolve
    ingest.py          # report -> samples (throughput derivation), heartbeat, evaluate, retain
    auth.py            # bearer guard, admin bootstrap, login rate limit, audit()
    migrate.py         # applies backend/migrations/*.sql once each
    routers/           # health, auth, groups, servers, agents, ingest (agent API),
                       # metrics, alerts, dashboard
  migrations/0001_initial.sql
  tests/               # pytest (SQLite override in conftest.py)
agent/
  src/infrapulse_agent/
    config.py          # JSON file + env config, token persistence (0600)
    collect.py         # psutil collectors (stateful for cpu deltas)
    client.py          # register/heartbeat/metrics with retry; AuthError stops
    __main__.py        # --once dry run + run loop
  systemd/infrapulse-agent.service
  tests/               # pytest (psutil mocked, HTTP stubbed)
frontend/
  src/
    api/client.ts      # axios + types + toParams()
    utils/             # health.ts (dots/classes/bar thresholds), format.ts (+ vitest)
    stores/auth.ts     # token in memory + localStorage (NEVER passwords);
    stores/settings.ts # theme + page size (localStorage)
    components/        # StatCard, TimeChart (svg line), MetricBar, Pagination, EmptyState
    views/             # Login, Overview, Servers, ServerDetail, ServerGroups,
                       # Agents, Alerts, Metrics, Settings
    router/index.ts    # requiresAuth guard
samples/               # demo agent config example (MANUAL walks through registration)
docs/screenshots/      # real headless-Chrome CDP captures (see MANUAL.md §15)
```

## Technology stack (preferred stack — do not change without user approval)

Vue 3 + TypeScript + Vite + Pinia + Vue Router · Python + uv + FastAPI +
Pydantic v2 + SQLAlchemy 2 · PostgreSQL 17 (plain tables, no extensions) ·
agent: Python + psutil + stdlib urllib · Docker/Compose. No other framework,
database, extension (TimescaleDB), or external notifier may be introduced silently.

## Coding conventions

- Backend: type-annotated Python, module docstring per file. Health logic
  lives ONLY in `health.py`; alert decisions ONLY in `alerting.py`; routers
  orchestrate. Thresholds come from `settings` — never literals.
- Metric identity is `(server_id, kind, name)` with `ts desc, id desc`
  tiebreaks; `latest_by_kind` assumes newest-first input.
- Throughput (`rx_bps`/`tx_bps`) is derived server-side from counter deltas;
  negative/huge deltas (counter reset) yield no sample. Never present
  cumulative counters as throughput.
- Agent API (`/api/agent/*`) authenticates by hashed token only; user JWTs
  are not accepted there and vice versa. Registration tokens are single-use
  + expiring; agent tokens are shown once and revocable.
- Secrets: bcrypt passwords, JWT bearer tokens, hashed agent tokens. Never
  log tokens; error responses stay generic (401 without oracle details).
- Frontend: Composition API + `<script setup lang="ts>`; mirrors of backend
  thresholds live in `utils/health.ts` for instant bar coloring, but the
  backend is authoritative (tests cover both sides). Dark-theme CSS variables.
- The agent must stay dependency-light (psutil + stdlib only) and
  crash-safe: every collector block is guarded; `AuthError` exits(2) for
  systemd visibility, transient errors back off.

## Dependency management

- Backend: `uv` with `backend/pyproject.toml` + committed `backend/uv.lock`.
- Agent: `uv` with `agent/pyproject.toml` (no lockfile committed; pin psutil
  in code review if reproducibility demands it).
- Frontend: npm with `frontend/package.json` (+ committed `package-lock.json`).
- Project-local envs: `backend/.venv`, `agent/.venv` (`uv sync` in each).

## Development commands

```sh
docker compose up --build          # needs .env with ADMIN_* set
docker compose up --build -d
docker compose logs -f backend
cd backend && uv sync && uv run pytest -q
cd backend && uv run uvicorn app.main:app --reload   # local Postgres + ADMIN_* env
cd agent && uv sync && uv run pytest -q
cd agent && AGENT_CONFIG=/tmp/agent.json uv run python -m infrapulse_agent --once
cd frontend && npm install && npm run dev             # Vite proxies /api → :8003
cd frontend && npm test && npm run build
```

## Testing commands

- `cd backend && uv run pytest -q` — 12 tests (health pure-logic, auth RBAC,
  server/group CRUD, registration single-use + revocation, ingest incl.
  throughput derivation, offline detection/resolution, alert fire/dedup/
  resolve, rules CRUD). Isolated in-memory SQLite; lifespan/`SessionLocal`
  redirected to the test session.
- `cd agent && uv run pytest -q` — 6 tests (collector shape, psutil-failure
  resilience, config precedence, registration validation, auth-error mapping).
- `cd frontend && npm test` — 7 vitest tests.

Never claim tests pass without running them in-session.

## Database conventions

- Schema owned by `backend/migrations/*.sql` via `schema_migrations`; new
  change = new numbered file; never edit an applied migration.
- `models.py` must stay SQLite-compatible (tests): no postgres-only
  constructs; BIGSERIAL is a migration-only type (model uses autoincrement Integer).
- Counts reference a table column (`with_entities(func.count(X.id))`).
- One row per (server, ts, kind, name); compound index
  `(server_id, kind, name, ts DESC)` serves latest + series queries.
- Cascades: server → agent/tokens/samples/alerts; group → servers SET NULL;
  rule → alerts SET NULL; user → notifications CASCADE.

## API conventions

- Routers under `/api`; Swagger at `/api/docs`. User routes need the bearer
  guard (`get_current_user`, stricter `require_admin` for destructive ops);
  agent routes need the agent-token guard.
- History/series endpoints are server-side with caps (page ≤100, points ≤2000).
- `latest` returns newest value per metric name (gauges, disk mounts, ifaces).
- `POST /api/alerts/evaluate` is the cron entry point; ingest auto-evaluates
  the reporting server and resolves its offline incident.

## Security requirements

- No unauthenticated monitoring or agent endpoints (except `/health`).
- Registration tokens: single-use, 24h expiry, hashed storage, shown once.
- Agent tokens: random 32-byte, sha256 storage, shown once, revocable.
- Login rate limiting (in-memory; single replica only).
- No remote shell/file/process control anywhere in agent or server.
- `.env` stays out of Git.

## Restrictions (need explicit user approval)

Changing frameworks/database, adding TimescaleDB or any extension, external
notifiers (email/Slack/webhook), SSO/LDAP, agent command execution or file
transfer, multi-replica shared state, downsampling/aggregation jobs, editing
applied migrations, restructuring services. Screenshots must always be real
captures of the running app (MANUAL.md §15) — never mockups. Keep docs
(`README.md`, `MANUAL.md`, `AGENTS.md`, `.env.example`) synchronized.
