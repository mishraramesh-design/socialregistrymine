# frontend — Config Console

Operator-facing UI: register connectors, review the Golden and Doubt registries,
manage consent purposes, configure delivery/eligibility rules, and trigger OpenG2P
syncs. Talks only to `api-gateway`, via **relative `/api/*` paths** — the production
image (`nginx.conf`) reverse-proxies those to `api-gateway` internally, so the whole
platform is reachable through nginx's single port with no API URL baked in at build
time. `npm run dev` mirrors this with a Vite dev-server proxy (see `vite.config.ts`)
pointed at `http://localhost:8000`. Set `VITE_API_BASE_URL` only to override with an
absolute URL.

Theme: near-black (`ink`) navigation and headings, white content surfaces, zinc/grey
for structure and secondary text, a single warm-yellow `accent` reserved for primary
actions and "needs attention" states (open doubt records, pending syncs) — so the
accent color always means something, never decoration.

## Run locally

```bash
npm install
npm run dev
```

Requires the backend services (`docker compose up` from the repo root, or each
service run individually) for data to appear — pages degrade gracefully to an
empty/error state if the gateway is unreachable.
