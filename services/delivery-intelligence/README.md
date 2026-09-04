# delivery-intelligence

Component B's core: scheme eligibility rules and inclusion/exclusion evaluation
(the Maharashtra case-study pattern — income threshold, asset ownership, duplicate
beneficiary — expressed as configured conditions rather than hardcoded logic).

If the citizen behind a request is still a Doubt Registry entry, eligibility isn't
decided — a `VerificationCase` is opened instead (intended to route to DIGIT's
field-verification workflow in the next build phase).

**Scaffold status**: threshold/field rule evaluator only, in-memory storage. This is
the seam for a learned exclusion/fraud-scoring model later.

Run: `uvicorn app.main:app --reload --port 8004` — docs at `/docs`.
