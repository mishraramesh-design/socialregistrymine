# Architecture Notes

See the root `README.md` for the component map and the Mermaid diagram. This file tracks decisions that don't belong in the top-level pitch.

## Golden Registry vs Doubt Registry

Every onboarding run of a new source database performs **two matches**, not one:

1. Match against the **Golden Registry** — confirms, enriches, or (rarely, and only via human review) reopens an existing golden record.
2. Match against the **Doubt Registry** — a new source may supply the distinguishing attribute that resolves a previously ambiguous cluster. Doubt records are never deleted by an automated process; they are only ever promoted to Golden by a human reviewer.

A record becomes a Doubt Registry entry when it is either:
- **not unique** — multiple existing records are plausible matches above the match threshold but none is decisively best, or
- **not complete** — insufficient attributes to classify confidently either way.

Every Doubt Registry entry carries the full evidence trail (candidate matches considered, per-field similarity scores, contributing source records) so a human reviewer isn't starting from scratch.

## Matching model strategy

- **Base model** (built — `services/registry-intelligence/app/matching/`): trained on generalizable, schema-agnostic similarity features — name (string similarity via rapidfuzz + phonetic via jellyfish), DOB (exact/same-month partial credit), and address (token-order-insensitive similarity). Four features, a logistic regression, trained on synthetic "same person re-entered with plausible noise" pairs (`train.py`) since no real client data exists yet. Retrained at Docker image build time so the shipped model always matches the code that trained it — nothing is committed as a binary artifact. Deterministic hard-identifier matching (Aadhaar/Ration/PAN) always runs first and short-circuits to score 1.0; the ML model only scores pairs that didn't already match deterministically.
- **Not yet built**: family/household graph structure as a feature (today's model only compares two individual records, not household context) and per-client fine-tuning. **Per-client fine-tuning** (design, not implemented): deterministic matches occurring naturally in a client's own data (e.g., two sources agreeing on the same Aadhaar) are free weak labels; human-resolved Doubt Registry entries are strong labels. Both would feed a periodic fine-tuning job — a lightweight recalibration on the base model, not a full retrain — once a real deployment has accumulated enough of either.
- **Cold start for a structurally new source**: as long as the new source's connector-config declares which columns are which *canonical feature type* (name/date/address/id), the base model can score matches immediately. Genuinely novel signal types (e.g. biometric similarity) require a new feature extractor, not just a config entry, and low-confidence matches from a new source type should default to the Doubt Registry rather than being force-classified (`MATCH_CONFIDENCE_THRESHOLD` controls this).

## DPG integration boundaries

None of Sunbird RC, Inji, OpenG2P, or DIGIT are forked or embedded in this repo. Each is deployed as its own on-prem service (see `deploy/`); this platform's services talk to them over their published REST APIs via a dedicated adapter (`sunbird-adapter`, `openg2p-sync`, `digit-adapter`, `inji-adapter`) so a DPG can be swapped or upgraded independently of the matching/eligibility logic.

`openg2p-sync` is intentionally **not** a live/real-time link — it is a manually-triggerable or cron-scheduled push of confirmed-eligible beneficiaries, so OpenG2P retains its own local copy for offline/connectivity resilience, per standard G2P deployment practice.

`digit-adapter` uses DIGIT's real `egov-workflow-v2` API (`RequestInfo`-wrapped process transitions) — verified against DIGIT's own API docs, not guessed — but routing a case requires a `BusinessService` to already exist on the target DIGIT instance (an operational setup step on DIGIT's side, out of this repo's scope).

`inji-adapter` issues credentials via OpenID4VCI **discovery** — it fetches Inji Certify's `/.well-known/openid-credential-issuer` metadata for the real `credential_endpoint` on every call rather than assuming a fixed path, since that's what the protocol specifies and it survives Inji Certify version changes. Its verification call against Inji Verify uses an **unconfirmed** path (`INJI_VERIFY_PATH`) — check it against whatever Inji Verify version is actually deployed.
