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

- **Base model**: trained once on generalizable, schema-agnostic similarity features — name (string + phonetic, tuned for Indian naming conventions), DOB, address (tokenized, hierarchy-aware), family/household graph structure, and deterministic ID overlap (Aadhaar/Ration/PAN when present). Ships pre-trained; works on a brand-new client with zero client data.
- **Per-client fine-tuning**: deterministic matches occurring naturally in that client's own data (e.g., two sources agreeing on the same Aadhaar) are free weak labels. Human-resolved Doubt Registry entries are strong labels. Both feed a periodic fine-tuning job — a lightweight adapter/recalibration on the base model, not a full retrain.
- **Cold start for a structurally new source**: as long as the new source's connector-config declares which columns are which *canonical feature type* (name/date/address/id), the base model can score matches immediately. Genuinely novel signal types (e.g. biometric similarity) require a new feature extractor, not just a config entry, and low-confidence matches from a new source type should default to the Doubt Registry rather than being force-classified.

## DPG integration boundaries

None of Sunbird RC, Inji, OpenG2P, or DIGIT are forked or embedded in this repo. Each is deployed as its own on-prem service; this platform's services talk to them over their published REST APIs via a dedicated adapter (`sunbird-adapter`, `openg2p-sync`) so a DPG can be swapped or upgraded independently of the matching/eligibility logic.

`openg2p-sync` is intentionally **not** a live/real-time link — it is a manually-triggerable or cron-scheduled push of confirmed-eligible beneficiaries, so OpenG2P retains its own local copy for offline/connectivity resilience, per standard G2P deployment practice.
