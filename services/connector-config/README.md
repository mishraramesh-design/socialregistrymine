# connector-config

No-code registration of a source database/API/file: connection details, field-to-canonical
schema mapping, refresh cadence, and the consent purpose it operates under. Adding a new
source is a `POST /connectors` call, not a new integration project.

Persisted (SQLite/SQLAlchemy). `POST /connectors/{id}/trigger-run` actually ingests
records into `registry-intelligence` — it's not just a status marker:

- **`api` connectors** fetch live: a GET to `connection_config["url"]`, expecting a JSON
  array of objects.
- **`database`/`flat_file` connectors** have no live driver yet — that's real per-DBMS
  integration work (a Postgres/MySQL/Oracle driver, credential handling), not a config
  change, and isn't built. Pass `records` in the trigger-run request body instead; the
  frontend's Connectors page does this as a paste-JSON panel.

Either way, each raw record is mapped through the connector's `schema_mapping` and POSTed
to registry-intelligence, and the run tracks how many landed as golden vs. doubt vs. failed
(`GET /connectors/{id}/runs`). Verified against a real running registry-intelligence,
including a fuzzy-duplicate re-run correctly merging into the existing golden record rather
than creating a second one.

Run: `uvicorn app.main:app --reload --port 8002` — docs at `/docs`.
