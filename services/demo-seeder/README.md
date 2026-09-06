# demo-seeder

Runs the platform's synthetic POC story — the same story as
`scripts/seed_demo.py` — from inside the deployment, so it can be triggered
with one click from the frontend ("Seed Demo Data" on the Dashboard) instead
of requiring shell/CLI access to the host.

It is a thin wrapper: all the actual work happens through `api-gateway`'s
public `/api/<service>/*` routes, exactly like the frontend or the standalone
script. This service adds nothing to the domain logic — it exists purely so
the seeding can be started from a browser.

State is in-memory and single-run-at-a-time: `POST /seed` starts a background
run (409 if one is already in progress), `GET /status` returns the running
log, final story summary, and error (if any). Not persisted — restarting the
container clears the last run's status, which is fine for a demo utility.

Uses a fixed random seed, so it tells the same story every run. It is **not**
idempotent: seeding twice against the same platform instance creates a second
batch of connectors and records — same caveat as `scripts/seed_demo.py`.

## Endpoints

- `POST /seed` — start a seed run (409 if already running)
- `GET /status` — `{status, started_at, finished_at, log, story, error}`
- `GET /health`

## Config

- `API_BASE_URL` — defaults to `http://api-gateway:8000` (internal Docker DNS)
- `GATEWAY_API_KEY` — set this to the same value as the gateway's, if any
