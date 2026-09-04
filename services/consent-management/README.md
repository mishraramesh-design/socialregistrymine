# consent-management

DPDP Act–aligned consent service. Every data-sharing action in the platform — a source
database being onboarded, a registry match being enriched, a delivery eligibility check
being run — is expected to reference a **purpose** registered here, and (where the data
principal is known) a **consent record**.

## Concepts

- **Purpose**: a registered reason data may be collected or shared (e.g. `ration-to-registry-match`,
  `registry-to-scheme-x-eligibility`). Config, not code — an operator registers a purpose once.
- **Consent record**: one data principal's grant (and, later, possible revocation) of a purpose.
  Carries the collection channel, who granted it, and an artifact version (so you know exactly
  what notice text the citizen saw).
- **Audit log**: append-only trail of every create/access/revoke action on a consent record.

## Run locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

Docs at `http://localhost:8001/docs`.

## API summary

| Method | Path | Purpose |
|---|---|---|
| POST | `/purposes` | Register a new purpose |
| GET | `/purposes` | List purposes |
| POST | `/consents` | Record a consent grant |
| GET | `/consents?data_principal_id=` | List a subject's consents |
| POST | `/consents/{id}/revoke` | Revoke a consent |
| GET | `/consents/{id}/audit` | Full audit trail for one consent |
| GET | `/health` | Liveness check |

## Tests

```bash
pytest
```
