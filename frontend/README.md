# frontend — Config Console

Operator-facing UI: register connectors, review the Golden and Doubt registries,
manage consent purposes, configure delivery/eligibility rules, and trigger OpenG2P
syncs. Talks only to `api-gateway` (`VITE_API_BASE_URL`, default `http://localhost:8000`).

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
