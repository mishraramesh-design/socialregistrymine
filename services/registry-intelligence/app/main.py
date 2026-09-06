"""registry-intelligence: entity resolution and the Golden/Doubt registry.

Every ingested record is matched against BOTH the Golden Registry and the
Doubt Registry (never just one), and a Doubt record is only ever promoted
or merged by a human reviewer via /doubt-records/{id}/resolve — never
automatically.

Matching runs two passes per ingest: deterministic (exact match on a hard
identifier — Aadhaar/national ID/ration ID) first, then the trained ML
model (app/matching/) scores every remaining record that wasn't already a
deterministic hit. This is the base model described in docs/architecture.md
— schema-agnostic name/DOB/address similarity, trained on synthetic data so
it works before any client's real data exists.
"""

import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import models
from .database import Base, engine, get_db
from .matching.features import name_similarity
from .matching.model import score_pair
from .schemas import (
    ClassificationLevel,
    DoubtRecordOut,
    DoubtResolution,
    GoldenRecordOut,
    IngestResult,
    MatchCandidate,
    RecordIngest,
)

os.makedirs("./data", exist_ok=True)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Registry Intelligence Service",
    description="Data standardization, entity resolution, and the Golden/Doubt Registry.",
    version="0.2.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

HARD_IDENTIFIER_FIELDS = ["aadhaar", "national_id", "ration_id"]

# A candidate only auto-merges when its score clears this bar. An exact hard-ID
# match is NOT automatically 1.0: two different people can share one identifier
# through a data-entry error, and that must surface as a doubt record for human
# review, not silently merge two different citizens into one golden record.
AUTO_MERGE_CONFIDENCE = 0.9


def _id_match_confidence(new_attrs: Dict[str, str], existing_attrs: Dict[str, str], field: str) -> tuple:
    """Scores an exact hard-identifier match, discounted if the name flatly
    contradicts it — corroboration, not blind trust in the identifier alone."""
    corroboration = name_similarity(new_attrs.get("name", ""), existing_attrs.get("name", ""))
    if not new_attrs.get("name") or not existing_attrs.get("name") or corroboration >= 0.5:
        return 1.0, f"exact match on {field}"
    return 0.5, f"exact match on {field}, but name differs significantly ({corroboration:.2f} similarity) — possible data error, needs review"


def match_record(db: Session, attributes: Dict[str, str]) -> List[MatchCandidate]:
    """Deterministic hard-identifier matching first, then ML scoring (see
    app/matching/model.py) against every record not already matched
    deterministically. O(n) over the registry per ingest — fine at pilot
    scale, not the design for a national-scale registry."""
    candidates: List[MatchCandidate] = []
    id_fields = {f: attributes[f] for f in HARD_IDENTIFIER_FIELDS if attributes.get(f)}
    threshold = float(os.getenv("MATCH_CONFIDENCE_THRESHOLD", "0.85"))

    golden_records = db.query(models.GoldenRecord).all()
    doubt_records = db.query(models.DoubtRecord).filter_by(status="open").all()

    matched_golden_ids, matched_doubt_ids = set(), set()

    for record in golden_records:
        for field, value in id_fields.items():
            if record.attributes.get(field) == value:
                score, evidence = _id_match_confidence(attributes, record.attributes, field)
                candidates.append(MatchCandidate(golden_record_id=record.id, score=score, evidence=evidence))
                matched_golden_ids.add(record.id)
                break
    for record in doubt_records:
        for field, value in id_fields.items():
            if record.attributes.get(field) == value:
                score, evidence = _id_match_confidence(attributes, record.attributes, field)
                candidates.append(MatchCandidate(doubt_record_id=record.id, score=score, evidence=evidence))
                matched_doubt_ids.add(record.id)
                break

    for record in golden_records:
        if record.id in matched_golden_ids:
            continue
        score = score_pair(attributes, record.attributes)
        if score >= threshold:
            candidates.append(
                MatchCandidate(golden_record_id=record.id, score=round(score, 3), evidence=f"ml_match score={score:.3f}")
            )
    for record in doubt_records:
        if record.id in matched_doubt_ids:
            continue
        score = score_pair(attributes, record.attributes)
        if score >= threshold:
            candidates.append(
                MatchCandidate(doubt_record_id=record.id, score=round(score, 3), evidence=f"ml_match score={score:.3f}")
            )

    return candidates


def classify(attributes: Dict[str, str], candidates: List[MatchCandidate]) -> ClassificationLevel:
    is_complete = all(attributes.get(f) for f in ["name", "date_of_birth", "address"])
    # Zero candidates -> unique (nothing to conflict with). One candidate -> unique
    # ONLY if it's confident enough to auto-merge; a single low-confidence
    # candidate (e.g. an ID match contradicted by name) is still an unresolved
    # conflict, not a clean match, and must go to doubt like 2+ candidates would.
    is_unique = len(candidates) == 0 or (len(candidates) == 1 and candidates[0].score >= AUTO_MERGE_CONFIDENCE)
    if is_unique and is_complete:
        return ClassificationLevel.UNIQUE_COMPLETE
    if is_unique and not is_complete:
        return ClassificationLevel.UNIQUE_INCOMPLETE
    if not is_unique and is_complete:
        return ClassificationLevel.COMPLETE_NOT_UNIQUE
    return ClassificationLevel.NEITHER


@app.post("/records/ingest", response_model=IngestResult, status_code=201)
def ingest_record(payload: RecordIngest, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    candidates = match_record(db, payload.attributes)
    classification = classify(payload.attributes, candidates)

    if classification in (ClassificationLevel.UNIQUE_COMPLETE, ClassificationLevel.UNIQUE_INCOMPLETE):
        if candidates and candidates[0].golden_record_id:
            golden = db.get(models.GoldenRecord, candidates[0].golden_record_id)
            golden.attributes = {**golden.attributes, **payload.attributes}
            golden.contributing_sources = [*golden.contributing_sources, payload.source_connector_id]
            golden.classification = classification.value
            golden.updated_at = now
        else:
            golden = models.GoldenRecord(
                attributes=payload.attributes,
                contributing_sources=[payload.source_connector_id],
                classification=classification.value,
                created_at=now,
                updated_at=now,
            )
            db.add(golden)
        db.commit()
        db.refresh(golden)
        return IngestResult(classification=classification, golden_record_id=golden.id, candidate_matches=candidates)

    doubt = models.DoubtRecord(
        attributes=payload.attributes,
        contributing_sources=[payload.source_connector_id],
        classification=classification.value,
        candidate_matches=[c.model_dump() for c in candidates],
        status="open",
        created_at=now,
    )
    db.add(doubt)
    db.commit()
    db.refresh(doubt)
    return IngestResult(classification=classification, doubt_record_id=doubt.id, candidate_matches=candidates)


@app.get("/golden-records", response_model=List[GoldenRecordOut])
def list_golden_records(db: Session = Depends(get_db)):
    return db.query(models.GoldenRecord).order_by(models.GoldenRecord.updated_at.desc()).all()


@app.get("/golden-records/{record_id}", response_model=GoldenRecordOut)
def get_golden_record(record_id: str, db: Session = Depends(get_db)):
    record = db.get(models.GoldenRecord, record_id)
    if not record:
        raise HTTPException(404, "Golden record not found")
    return record


@app.get("/doubt-records", response_model=List[DoubtRecordOut])
def list_doubt_records(status: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(models.DoubtRecord)
    if status:
        query = query.filter_by(status=status)
    return query.order_by(models.DoubtRecord.created_at.desc()).all()


@app.get("/doubt-records/{record_id}", response_model=DoubtRecordOut)
def get_doubt_record(record_id: str, db: Session = Depends(get_db)):
    record = db.get(models.DoubtRecord, record_id)
    if not record:
        raise HTTPException(404, "Doubt record not found")
    return record


@app.post("/doubt-records/{record_id}/resolve", response_model=DoubtRecordOut)
def resolve_doubt_record(record_id: str, payload: DoubtResolution, db: Session = Depends(get_db)):
    """The only way a Doubt record leaves the queue — always a human decision."""
    doubt = db.get(models.DoubtRecord, record_id)
    if not doubt:
        raise HTTPException(404, "Doubt record not found")
    if doubt.status == "resolved":
        raise HTTPException(409, "Doubt record already resolved")

    now = datetime.now(timezone.utc)
    if payload.action == "merge_into_golden":
        if not payload.target_golden_record_id:
            raise HTTPException(422, "target_golden_record_id is required for merge_into_golden")
        golden = db.get(models.GoldenRecord, payload.target_golden_record_id)
        if not golden:
            raise HTTPException(422, "target_golden_record_id must reference an existing golden record")
        golden.attributes = {**golden.attributes, **doubt.attributes}
        golden.contributing_sources = [*golden.contributing_sources, *doubt.contributing_sources]
        golden.updated_at = now
    elif payload.action == "promote_to_new_golden":
        golden = models.GoldenRecord(
            attributes=doubt.attributes,
            contributing_sources=doubt.contributing_sources,
            classification=ClassificationLevel.UNIQUE_COMPLETE.value,
            created_at=now,
            updated_at=now,
        )
        db.add(golden)
    else:
        raise HTTPException(422, "action must be 'merge_into_golden' or 'promote_to_new_golden'")

    doubt.status = "resolved"
    doubt.resolved_at = now
    doubt.resolved_by = payload.resolved_by
    doubt.resolution = payload.action
    db.commit()
    db.refresh(doubt)
    return doubt


@app.get("/health")
def health():
    return {"status": "ok", "service": "registry-intelligence"}
