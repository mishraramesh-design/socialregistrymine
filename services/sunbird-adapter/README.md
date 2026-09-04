# sunbird-adapter

The single integration point with a separately-deployed Sunbird RC instance (kept
separate per the decision to run Sunbird RC as its own service, not embedded).
`registry-intelligence` calls this service once a record is confirmed golden;
this service owns the Sunbird RC-specific API shape (`/api/v1/Citizen` schema
registration) so that detail never leaks into the matching engine.

Run: `uvicorn app.main:app --reload --port 8006` — docs at `/docs`.
