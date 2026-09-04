# registry-intelligence

The core of Component A. Ingests standardized records, matches them against **both** the
Golden Registry and the Doubt Registry, classifies them (see `docs/architecture.md` at the
repo root for the four levels), and stores the result.

**Doubt records are never auto-resolved** — `POST /doubt-records/{id}/resolve` is the only
way out of the queue, and it always takes a human `resolved_by`.

**Scaffold status**: `match_record()` implements deterministic (exact hard-identifier)
matching only, as the seam for the fuzzy/ML matching model described in the architecture
doc. Storage is in-memory.

Run: `uvicorn app.main:app --reload --port 8003` — docs at `/docs`.
