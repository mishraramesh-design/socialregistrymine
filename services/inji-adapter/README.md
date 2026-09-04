# inji-adapter

Issues portable, verifiable credentials for a golden record's identity/eligibility
via a separately-deployed Inji Certify (issuance) and Inji Verify (verification)
instance — so a citizen can present proof at a service point without that point
re-querying the registry every time.

Issuance is OpenID4VCI-based and **discovery-driven**: this adapter fetches Inji
Certify's `/.well-known/openid-credential-issuer` metadata to find the real
`credential_endpoint` on every call, rather than assuming a fixed path — that's
what the protocol expects, and it means this adapter doesn't need updating if
Inji Certify's internal routing changes across versions.

**Before this works against a real instance**:
- `INJI_TOKEN_URL`, `INJI_CLIENT_ID`, `INJI_CLIENT_SECRET` — OAuth2 client
  credentials, issued by whoever operates the Inji Certify instance. Not
  something this adapter can generate.
- `INJI_VERIFY_PATH` — defaults to a best-guess path; **unconfirmed** against a
  live Inji Verify instance. Check it against the deployed version's own API docs
  before relying on verification results.

Run: `uvicorn app.main:app --reload --port 8008` — docs at `/docs`.
