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

import os
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import models
from .database import Base, engine, get_db
from .schemas import (
    ComparisonOp,
    EligibilityCheckRequest,
    EligibilityResult,
    SchemeRuleCreate,
    SchemeRuleOut,
    VerificationCaseOut,
)

os.makedirs("./data", exist_ok=True)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Delivery Intelligence Service",
    description="Eligibility scoring, inclusion/exclusion logic, and verification-case creation.",
    version="0.2.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _evaluate(op: str, actual: float, expected: float) -> bool:
    return {
        ComparisonOp.EQ: actual == expected,
        ComparisonOp.LT: actual < expected,
        ComparisonOp.LTE: actual <= expected,
        ComparisonOp.GT: actual > expected,
        ComparisonOp.GTE: actual >= expected,
    }[ComparisonOp(op)]


@app.post("/schemes", response_model=SchemeRuleOut, status_code=201)
def create_scheme(payload: SchemeRuleCreate, db: Session = Depends(get_db)):
    if db.query(models.SchemeRule).filter_by(scheme_code=payload.scheme_code).first():
        raise HTTPException(409, f"Scheme '{payload.scheme_code}' already registered")
    scheme = models.SchemeRule(**payload.model_dump(mode="json"))
    db.add(scheme)
    db.commit()
    db.refresh(scheme)
    return scheme


@app.get("/schemes", response_model=List[SchemeRuleOut])
def list_schemes(db: Session = Depends(get_db)):
    return db.query(models.SchemeRule).order_by(models.SchemeRule.created_at.desc()).all()


@app.post("/eligibility/check", response_model=EligibilityResult)
def check_eligibility(payload: EligibilityCheckRequest, db: Session = Depends(get_db)):
    if payload.citizen_doubt_record_id and not payload.citizen_golden_record_id:
        case = models.VerificationCase(
            reason="Identity unresolved in Doubt Registry — eligibility cannot be decided until a human "
            "reviewer resolves it.",
            citizen_doubt_record_id=payload.citizen_doubt_record_id,
            scheme_code=payload.scheme_code,
            status="open",
        )
        db.add(case)
        db.commit()
        db.refresh(case)
        return EligibilityResult(eligible=False, scheme_code=payload.scheme_code, verification_case_id=case.id)

    scheme = db.query(models.SchemeRule).filter_by(scheme_code=payload.scheme_code).first()
    if not scheme:
        raise HTTPException(404, f"Scheme '{payload.scheme_code}' is not registered")

    failed = []
    for cond in scheme.eligibility_conditions:
        actual = payload.attributes.get(cond["field"])
        if actual is None or not _evaluate(cond["op"], actual, cond["value"]):
            failed.append(f"{cond['field']} {cond['op']} {cond['value']}")

    excluded_by = []
    for cond in scheme.exclusion_conditions:
        actual = payload.attributes.get(cond["field"])
        if actual is not None and _evaluate(cond["op"], actual, cond["value"]):
            excluded_by.append(f"{cond['field']} {cond['op']} {cond['value']}")

    eligible = not failed and not excluded_by
    return EligibilityResult(
        eligible=eligible,
        scheme_code=payload.scheme_code,
        failed_conditions=failed,
        excluded_by=excluded_by,
    )


@app.get("/verification-cases", response_model=List[VerificationCaseOut])
def list_verification_cases(status: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(models.VerificationCase)
    if status:
        query = query.filter_by(status=status)
    return query.order_by(models.VerificationCase.created_at.desc()).all()


@app.get("/health")
def health():
    return {"status": "ok", "service": "delivery-intelligence"}
