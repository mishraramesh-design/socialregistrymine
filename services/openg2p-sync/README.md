# openg2p-sync

Pushes confirmed-eligible beneficiaries into a separately-deployed OpenG2P instance.
`OPENG2P_SYNC_MODE=manual` (default) means sync only happens via `POST /sync/trigger`;
set it to `scheduled` and configure `OPENG2P_SYNC_CRON` to run it periodically instead
(the actual scheduler — e.g. a cron sidecar or APScheduler — is a next-phase addition;
`GET /sync/schedule` exposes the configured intent today).

Every run is recorded (`GET /sync/runs`) with success/failure and count synced, so a
failed push to OpenG2P is visible and retryable rather than silent.

Run: `uvicorn app.main:app --reload --port 8005` — docs at `/docs`.
