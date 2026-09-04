# digit-adapter

Routes Doubt Registry verification cases (opened by `delivery-intelligence` when a
citizen's identity is unresolved) to a separately-deployed DIGIT instance's workflow
engine (`egov-workflow-v2`) for field-agent verification.

Uses DIGIT's real, documented API shape: a `RequestInfo`-wrapped
`POST /egov-workflow-v2/egov-wf/process/_transition` to create the process, and
`/process/_search` to poll status — not a guessed endpoint.

**Before this works against a real DIGIT instance**, two things need doing on the
DIGIT side (operational setup, not something this adapter can do for you):
1. Create a `BusinessService` (workflow definition) for registry verification —
   set its code via `DIGIT_BUSINESS_SERVICE` (default `REGISTRY_VERIFICATION`).
2. Obtain an employee auth token from DIGIT's own `/user/oauth/token` login
   endpoint and set `DIGIT_AUTH_TOKEN` — this adapter doesn't mint credentials.

Run: `uvicorn app.main:app --reload --port 8007` — docs at `/docs`.
