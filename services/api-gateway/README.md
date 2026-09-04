# api-gateway

Routes `/api/<service>/*` to the matching backend (`consent`, `connectors`, `registry`,
`delivery`, `openg2p-sync`, `sunbird`, `digit`, `inji`). `GET /health` pings every
downstream service and reports an aggregate status — useful for the frontend's
dashboard, and deliberately not behind the API key gate (see below) so infra
monitoring doesn't need the application secret.

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
