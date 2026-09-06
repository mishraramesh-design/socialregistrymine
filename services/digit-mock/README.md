# digit-mock

**Not real DIGIT.** DIGIT is a large, Kubernetes-first platform (see
`deploy/README.md` for why standing up a real cluster is out of scope for this
POC). This is a ~100-line stand-in implementing the exact two
`egov-workflow-v2` endpoints `digit-adapter` actually calls
(`/process/_transition`, `/process/_search`), using DIGIT's real
`RequestInfo`/`ProcessInstances` request shape, so the "doubt record gets
routed for field verification, and comes back resolved" story demos
end-to-end.

Each routed case auto-progresses through `PENDING_ASSIGNMENT` →
`FIELD_VISIT_SCHEDULED` → `VERIFIED` over ~25 seconds of wall-clock time,
purely so polling status a couple of times during a demo shows movement —
this is illustrative, not a workflow engine, and has none of DIGIT's actual
business logic (approvals, SLAs, multi-tenancy, audit).

**Point `digit-adapter`'s `DIGIT_BASE_URL` at this service** instead of a
real DIGIT deployment. When you're ready for the real thing, swap it for an
actual DIGIT cluster — the API shape is identical, nothing else changes.

Run: `uvicorn app.main:app --reload --port 8083` — docs at `/docs`.
