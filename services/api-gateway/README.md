# api-gateway

Routes `/api/<service>/*` to the matching backend (`consent`, `connectors`, `registry`,
`delivery`, `openg2p-sync`, `sunbird`, `digit`, `inji`, `demo`). `GET /health` pings every
downstream service and reports an aggregate status — useful for the frontend's
dashboard, and deliberately not behind the API key gate (see below) so infra
monitoring doesn't need the application secret. Also registered at `GET /api/health`
(same handler) — **use this path from the frontend**, not the bare one: nginx's
production config only proxies paths under `/api/` (see `frontend/nginx.conf`), so a
browser request to a bare `/health` never reaches this service, it falls through to
the SPA's own `index.html` instead.

`GET /api/audit/timeline` aggregates every auditable action across every service —
consent grants/revocations, ingestion runs, golden record creation, doubt
flags/resolutions, verification cases, DIGIT routing, Sunbird RC pushes, and OpenG2P
syncs — into one chronological trail, normalized into a common `{timestamp, service,
action, actor, summary, detail}` shape and sorted newest-first. Best-effort per
service: a slow or unreachable service just contributes no events rather than failing
the whole call. Powers the frontend's **Audit Trail** page. Every adapter's own
`/health` (sunbird, digit, inji, openg2p-sync) also reports a `downstream` field —
a real reachability probe of the DPG behind it, not just this adapter's own liveness —
which powers the frontend's **System Map** page.

## Auth

Set `GATEWAY_API_KEY` to require an `X-API-Key` header on every `/api/*` call —
unset (the default) means no auth, for frictionless local dev. This is a shared
secret, not per-user auth: it's meant for machine-to-machine callers (an external
system calling this platform's API), not the operator console.

**Important limitation**: the `frontend` config console currently calls the gateway
with no key. A browser-side app can't keep a secret anyway — embedding
`GATEWAY_API_KEY` in frontend JS would defeat the point of it. So don't set
`GATEWAY_API_KEY` for a deployment where operators use the frontend, until the
frontend has real user authentication (SSO/login) in front of it — until then,
restrict access to the console (network-level: VPN, IP allowlist, or an
authenticating reverse proxy) rather than relying on this gateway key. Rate
limiting has the same "not implemented yet" status.

Run: `uvicorn app.main:app --reload --port 8000`.
