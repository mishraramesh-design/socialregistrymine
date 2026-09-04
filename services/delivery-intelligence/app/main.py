"""delivery-intelligence: eligibility scoring and inclusion/exclusion for Component B.

Reads golden-record attributes (normally fetched from registry-intelligence /
sunbird-adapter) and scores them against a scheme's configured rules. A
threshold/field-based rule evaluator ships here as the baseline; this is the
seam for a learned exclusion/fraud-scoring model later (duplicate-beneficiary
detection, leakage patterns) without changing the API contract.

When a citizen's golden record is itself a Doubt Registry entry (identity
still unresolved), eligibility can't be decided — a verification case is
opened instead, intended to be routed to DIGIT's field-verification workflow.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(
    title="Delivery Intelligence Service",
    description="Eligibility scoring, inclusion/exclusion logic, and verification-case creation.",
    version="0.1.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class ComparisonOp(str, Enum):
    EQ = "eq"
    LT = "lt"
    LTE = "lte"
    GT = "gt"
    GTE = "gte"


class RuleCondition(BaseModel):
    field: str
    op: ComparisonOp
    value: float


class SchemeRuleCreate(BaseModel):
    scheme_code: str
    name: str
    eligibility_conditions: List[RuleCondition] = Field(default_factory=list, description="ALL must pass")
    exclusion_conditions: List[RuleCondition] = Field(default_factory=list, description="ANY match excludes")


class SchemeRule(SchemeRuleCreate):
    id: str
    created_at: datetime


class EligibilityCheckRequest(BaseModel):
    citizen_golden_record_id: Optional[str] = None
    citizen_doubt_record_id: Optional[str] = None
    scheme_code: str
    attributes: Dict[str, float]


class EligibilityResult(BaseModel):
    eligible: bool
    scheme_code: str
    failed_conditions: List[str] = []
    excluded_by: List[str] = []
    verification_case_id: Optional[str] = None


class VerificationCase(BaseModel):
    id: str
    reason: str
    citizen_doubt_record_id: Optional[str]
    scheme_code: str
    status: str = "open"
    created_at: datetime


_schemes: Dict[str, SchemeRule] = {}
_verification_cases: Dict[str, VerificationCase] = {}


def _evaluate(op: ComparisonOp, actual: float, expected: float) -> bool:
    return {
        ComparisonOp.EQ: actual == expected,
        ComparisonOp.LT: actual < expected,
        ComparisonOp.LTE: actual <= expected,
        ComparisonOp.GT: actual > expected,
        ComparisonOp.GTE: actual >= expected,
    }[op]


@app.post("/schemes", response_model=SchemeRule, status_code=201)
def create_scheme(payload: SchemeRuleCreate):
    if payload.scheme_code in {s.scheme_code for s in _schemes.values()}:
        raise HTTPException(409, f"Scheme '{payload.scheme_code}' already registered")
    scheme = SchemeRule(id=str(uuid.uuid4()), created_at=datetime.now(timezone.utc), **payload.model_dump())
    _schemes[scheme.id] = scheme
    return scheme


@app.get("/schemes", response_model=List[SchemeRule])
def list_schemes():
    return list(_schemes.values())


@app.post("/eligibility/check", response_model=EligibilityResult)
def check_eligibility(payload: EligibilityCheckRequest):
    if payload.citizen_doubt_record_id and not payload.citizen_golden_record_id:
        case = VerificationCase(
            id=str(uuid.uuid4()),
            reason="Identity unresolved in Doubt Registry — eligibility cannot be decided until a human "
            "reviewer resolves it.",
            citizen_doubt_record_id=payload.citizen_doubt_record_id,
            scheme_code=payload.scheme_code,
            created_at=datetime.now(timezone.utc),
        )
        _verification_cases[case.id] = case
        return EligibilityResult(eligible=False, scheme_code=payload.scheme_code, verification_case_id=case.id)

    scheme = next((s for s in _schemes.values() if s.scheme_code == payload.scheme_code), None)
    if not scheme:
        raise HTTPException(404, f"Scheme '{payload.scheme_code}' is not registered")

    failed = []
    for cond in scheme.eligibility_conditions:
        actual = payload.attributes.get(cond.field)
        if actual is None or not _evaluate(cond.op, actual, cond.value):
            failed.append(f"{cond.field} {cond.op.value} {cond.value}")

    excluded_by = []
    for cond in scheme.exclusion_conditions:
        actual = payload.attributes.get(cond.field)
        if actual is not None and _evaluate(cond.op, actual, cond.value):
            excluded_by.append(f"{cond.field} {cond.op.value} {cond.value}")

    eligible = not failed and not excluded_by
    return EligibilityResult(
        eligible=eligible,
        scheme_code=payload.scheme_code,
        failed_conditions=failed,
        excluded_by=excluded_by,
    )


@app.get("/verification-cases", response_model=List[VerificationCase])
def list_verification_cases(status: Optional[str] = None):
    cases = list(_verification_cases.values())
    if status:
        cases = [c for c in cases if c.status == status]
    return cases


@app.get("/health")
def health():
    return {"status": "ok", "service": "delivery-intelligence"}
