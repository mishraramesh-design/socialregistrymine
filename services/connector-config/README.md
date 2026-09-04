# connector-config

No-code registration of a source database/API/file: connection details, field-to-canonical
schema mapping, refresh cadence, and the consent purpose it operates under. Adding a new
source is a `POST /connectors` call, not a new integration project.

**Scaffold status**: in-memory store, `/trigger-run` only records intent. Next phase wires
`trigger-run` to actually invoke `registry-intelligence`'s ingestion pipeline and persists
connectors to a real database.

Run: `uvicorn app.main:app --reload --port 8002` — docs at `/docs`.
