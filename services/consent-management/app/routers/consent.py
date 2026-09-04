from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/consents", tags=["consents"])


def _log(db: Session, consent_id: str, action: str, actor: str, details: str | None = None):
    db.add(models.ConsentAuditLog(consent_id=consent_id, action=action, actor=actor, details=details))


@router.post("", response_model=schemas.ConsentOut, status_code=201)
def create_consent(payload: schemas.ConsentCreate, db: Session = Depends(get_db)):
    purpose = db.query(models.ConsentPurpose).filter_by(code=payload.purpose_code).first()
    if not purpose:
        raise HTTPException(404, f"Unknown purpose code '{payload.purpose_code}'. Register it first via /purposes.")

    consent = models.ConsentRecord(
        data_principal_id=payload.data_principal_id,
        purpose_id=purpose.id,
        collection_channel=payload.collection_channel,
        granted_by=payload.granted_by,
        consent_artifact_version=payload.consent_artifact_version,
        expires_at=payload.expires_at,
    )
    db.add(consent)
    db.flush()
    _log(db, consent.id, "created", payload.granted_by, f"purpose={purpose.code}")
    db.commit()
    db.refresh(consent)
    return consent


@router.get("/{consent_id}", response_model=schemas.ConsentOut)
def get_consent(consent_id: str, db: Session = Depends(get_db)):
    consent = _get_or_404(db, consent_id)
    _log(db, consent.id, "accessed", "system")
    db.commit()
    return consent


@router.get("", response_model=list[schemas.ConsentOut])
def list_consents(data_principal_id: str | None = None, db: Session = Depends(get_db)):
    query = db.query(models.ConsentRecord)
    if data_principal_id:
        query = query.filter_by(data_principal_id=data_principal_id)
    return query.order_by(models.ConsentRecord.granted_at.desc()).all()


@router.post("/{consent_id}/revoke", response_model=schemas.ConsentOut)
def revoke_consent(consent_id: str, payload: schemas.ConsentRevoke, db: Session = Depends(get_db)):
    consent = _get_or_404(db, consent_id)
    if consent.status == models.ConsentStatus.REVOKED:
        raise HTTPException(409, "Consent already revoked")

    consent.status = models.ConsentStatus.REVOKED
    consent.revoked_at = datetime.now(timezone.utc)
    consent.revocation_reason = payload.reason
    _log(db, consent.id, "revoked", payload.actor, payload.reason)
    db.commit()
    db.refresh(consent)
    return consent


@router.get("/{consent_id}/audit", response_model=list[schemas.AuditEntryOut])
def get_audit_trail(consent_id: str, db: Session = Depends(get_db)):
    _get_or_404(db, consent_id)
    return (
        db.query(models.ConsentAuditLog)
        .filter_by(consent_id=consent_id)
        .order_by(models.ConsentAuditLog.timestamp)
        .all()
    )


def _get_or_404(db: Session, consent_id: str) -> models.ConsentRecord:
    consent = db.get(models.ConsentRecord, consent_id)
    if not consent:
        raise HTTPException(404, "Consent record not found")
    return consent
