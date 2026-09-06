# scripts/

**Prefer not to use a terminal?** The exact same story is one click away in the
frontend itself — open the Dashboard and hit **Seed Demo Data**. That button calls
`services/demo-seeder/`, a small service that runs this same logic server-side
through `api-gateway`'s own APIs. This CLI script is still useful for automation
or when you want the log printed to your own terminal instead of the browser.

## seed_demo.py

Seeds a complete, narratable POC story through the platform's real APIs (no
service internals touched) — three fake Delhi source databases, ~20 synthetic
residents with deliberate overlaps, one real benefit scheme, and both
Doubt-Registry resolution paths (human review, and routing to DIGIT for field
verification). See the module docstring for the full story it tells.

Verified against real running services end to end multiple times while
building it — it caught two genuine bugs in the matching logic along the way
(see `docs/architecture.md` / `services/registry-intelligence/app/matching/`
for what changed): missing fields being scored as "actively different" rather
than "no signal," and a single exact-ID match being trusted even when the name
flatly contradicted it. Both are fixed; the fixes are what make this script's
merge scenarios actually work.

**A note on the synthetic data**: names are drawn from a deliberately small,
realistic-sounding pool. On any given run you may see one or two additional
records land in the Doubt Registry beyond the ones explicitly engineered as
conflicts — that's the matcher correctly flagging genuine ambiguity from
shared surnames/initials in a small name pool, the same way it would on real
data with common names. It's not a bug to chase; if anything it's a fair
preview of what a real deployment's Doubt Registry looks like.

### Usage

```bash
pip install -r requirements.txt

# Against a local docker compose stack:
python seed_demo.py

# Against a deployed platform (e.g. your Hostinger instance):
API_BASE_URL=http://<host>:6561 python seed_demo.py
# (if your gateway has GATEWAY_API_KEY set)
GATEWAY_API_KEY=<key> API_BASE_URL=http://<host>:6561 python seed_demo.py
```

The script uses a fixed random seed — it tells the same story every run
(useful for rehearsing a demo), but is **not idempotent**: running it twice
against the same platform instance creates a second batch of connectors and
records. Start from a fresh database (or a fresh `docker compose up`) between
runs, or accept the duplication if you're just re-exercising the pipeline.

After seeding, open the frontend and walk through: Connectors (see the 3
registered sources and their run history), Golden Registry (the merged and
single-source citizens), Doubt Registry (review and resolve the remaining
conflict), Delivery Rules (the registered scheme and its eligibility
outcomes).
