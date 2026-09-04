"""registry-intelligence: entity resolution and the Golden/Doubt registry.

Every ingested record is matched against BOTH the Golden Registry and the
Doubt Registry (never just one), and a Doubt record is only ever promoted
or merged by a human reviewer via /doubt-records/{id}/resolve — never
automatically.

`match_record()` is deliberately isolated: it currently runs a simple
deterministic check (exact match on a hard identifier such as Aadhaar/
national ID/ration ID). This is the seam where the trained ML model
(deterministic + fuzzy + learned similarity, per docs/architecture.md)
plugs in without changing the ingest/classify/store flow around it.

Storage is in-memory for this scaffold phase.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(
    title="Registry Intelligence Service",
    description="Data standardization, entity resolution, and the Golden/Doubt Registry.",
    version="0.1.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

HARD_IDENTIFIER_FIELDS = ["aadhaar", "national_id", "ration_id"]


class ClassificationLevel(str, Enum):
    UNIQUE_COMPLETE = "L1_unique_complete"           # -> Golden Registry
    UNIQUE_INCOMPLETE = "L2_unique_incomplete"        # -> Golden Registry, flagged for enrichment
    COMPLETE_NOT_UNIQUE = "L3_complete_not_unique"    # -> Doubt Registry
    NEITHER = "L4_not_unique_not_complete"            # -> Doubt Registry


class RecordIngest(BaseModel):
    source_connector_id: str
    source_record_id: str
    attributes: Dict[str, str] = Field(..., description="Canonical-schema fields for this record")


class MatchCandidate(BaseModel):
    golden_record_id: Optional[str] = None
    doubt_record_id: Optional[str] = None
    score: float
    evidence: str


class GoldenRecord(BaseModel):
    id: str
    attributes: Dict[str, str]
    contributing_sources: List[str]
    classification: ClassificationLevel
    created_at: datetime
    updated_at: datetime


class DoubtRecord(BaseModel):
    id: str
    attributes: Dict[str, str]
    contributing_sources: List[str]
    classification: ClassificationLevel
    candidate_matches: List[MatchCandidate]
    status: str = "open"  # open | resolved
    created_at: datetime
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution: Optional[str] = None


class DoubtResolution(BaseModel):
    resolved_by: str
    action: str = Field(..., description="'merge_into_golden' or 'promote_to_new_golden'")
    target_golden_record_id: Optional[str] = Field(None, description="Required when action=merge_into_golden")
    notes: Optional[str] = None


class IngestResult(BaseModel):
    classification: ClassificationLevel
    golden_record_id: Optional[str] = None
    doubt_record_id: Optional[str] = None
    candidate_matches: List[MatchCandidate] = []


_golden: Dict[str, GoldenRecord] = {}
_doubt: Dict[str, DoubtRecord] = {}


def match_record(attributes: Dict[str, str]) -> List[MatchCandidate]:
    """Deterministic baseline matcher: exact match on a hard identifier against every
    existing Golden and Doubt record. Replace/extend with the trained fuzzy + ML
    similarity model — this function's signature (attributes in, scored candidates
    out) is the integration point."""
    candidates: List[MatchCandidate] = []
    id_fields = {f: attributes[f] for f in HARD_IDENTIFIER_FIELDS if attributes.get(f)}
    if not id_fields:
        return candidates

    for gid, record in _golden.items():
        for field, value in id_fields.items():
            if record.attributes.get(field) == value:
                candidates.append(MatchCandidate(golden_record_id=gid, score=1.0, evidence=f"exact match on {field}"))
                break
    for did, record in _doubt.items():
        if record.status != "open":
            continue
        for field, value in id_fields.items():
            if record.attributes.get(field) == value:
                candidates.append(MatchCandidate(doubt_record_id=did, score=1.0, evidence=f"exact match on {field}"))
                break
    return candidates


def classify(attributes: Dict[str, str], candidates: List[MatchCandidate]) -> ClassificationLevel:
    is_complete = all(attributes.get(f) for f in ["name", "date_of_birth", "address"])
    is_unique = len(candidates) <= 1
    if is_unique and is_complete:
        return ClassificationLevel.UNIQUE_COMPLETE
    if is_unique and not is_complete:
        return ClassificationLevel.UNIQUE_INCOMPLETE
    if not is_unique and is_complete:
        return ClassificationLevel.COMPLETE_NOT_UNIQUE
    return ClassificationLevel.NEITHER


@app.post("/records/ingest", response_model=IngestResult, status_code=201)
def ingest_record(payload: RecordIngest):
    now = datetime.now(timezone.utc)
    candidates = match_record(payload.attributes)
    classification = classify(payload.attributes, candidates)

    if classification in (ClassificationLevel.UNIQUE_COMPLETE, ClassificationLevel.UNIQUE_INCOMPLETE):
        if candidates and candidates[0].golden_record_id:
            golden = _golden[candidates[0].golden_record_id]
            golden.attributes.update(payload.attributes)
            golden.contributing_sources.append(payload.source_connector_id)
            golden.classification = classification
            golden.updated_at = now
        else:
            golden = GoldenRecord(
                id=str(uuid.uuid4()),
                attributes=payload.attributes,
                contributing_sources=[payload.source_connector_id],
                classification=classification,
                created_at=now,
                updated_at=now,
            )
            _golden[golden.id] = golden
        return IngestResult(classification=classification, golden_record_id=golden.id, candidate_matches=candidates)

    doubt = DoubtRecord(
        id=str(uuid.uuid4()),
        attributes=payload.attributes,
        contributing_sources=[payload.source_connector_id],
        classification=classification,
        candidate_matches=candidates,
        created_at=now,
    )
    _doubt[doubt.id] = doubt
    return IngestResult(classification=classification, doubt_record_id=doubt.id, candidate_matches=candidates)


@app.get("/golden-records", response_model=List[GoldenRecord])
def list_golden_records():
    return list(_golden.values())


@app.get("/golden-records/{record_id}", response_model=GoldenRecord)
def get_golden_record(record_id: str):
    record = _golden.get(record_id)
    if not record:
        raise HTTPException(404, "Golden record not found")
    return record


@app.get("/doubt-records", response_model=List[DoubtRecord])
def list_doubt_records(status: Optional[str] = None):
    records = list(_doubt.values())
    if status:
        records = [r for r in records if r.status == status]
    return records


@app.get("/doubt-records/{record_id}", response_model=DoubtRecord)
def get_doubt_record(record_id: str):
    record = _doubt.get(record_id)
    if not record:
        raise HTTPException(404, "Doubt record not found")
    return record


@app.post("/doubt-records/{record_id}/resolve", response_model=DoubtRecord)
def resolve_doubt_record(record_id: str, payload: DoubtResolution):
    """The only way a Doubt record leaves the queue — always a human decision."""
    doubt = _doubt.get(record_id)
    if not doubt:
        raise HTTPException(404, "Doubt record not found")
    if doubt.status == "resolved":
        raise HTTPException(409, "Doubt record already resolved")

    now = datetime.now(timezone.utc)
    if payload.action == "merge_into_golden":
        if not payload.target_golden_record_id or payload.target_golden_record_id not in _golden:
            raise HTTPException(422, "target_golden_record_id must reference an existing golden record")
        golden = _golden[payload.target_golden_record_id]
        golden.attributes.update(doubt.attributes)
        golden.contributing_sources.extend(doubt.contributing_sources)
        golden.updated_at = now
    elif payload.action == "promote_to_new_golden":
        golden = GoldenRecord(
            id=str(uuid.uuid4()),
            attributes=doubt.attributes,
            contributing_sources=doubt.contributing_sources,
            classification=ClassificationLevel.UNIQUE_COMPLETE,
            created_at=now,
            updated_at=now,
        )
        _golden[golden.id] = golden
    else:
        raise HTTPException(422, "action must be 'merge_into_golden' or 'promote_to_new_golden'")

    doubt.status = "resolved"
    doubt.resolved_at = now
    doubt.resolved_by = payload.resolved_by
    doubt.resolution = payload.action
    return doubt


@app.get("/health")
def health():
    return {"status": "ok", "service": "registry-intelligence"}
