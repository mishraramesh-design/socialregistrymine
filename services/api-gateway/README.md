# api-gateway

Routes `/api/<service>/*` to the matching backend (`consent`, `connectors`, `registry`,
`delivery`, `openg2p-sync`, `sunbird`). `GET /health` pings every downstream service and
reports an aggregate status — useful for the frontend's dashboard.

Auth (SSO/API keys) and rate limiting belong here in a real deployment; not implemented
in this scaffold.

Run: `uvicorn app.main:app --reload --port 8000`.
