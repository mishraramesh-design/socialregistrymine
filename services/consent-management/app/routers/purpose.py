from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/purposes", tags=["purposes"])


@router.post("", response_model=schemas.PurposeOut, status_code=201)
def create_purpose(payload: schemas.PurposeCreate, db: Session = Depends(get_db)):
    existing = db.query(models.ConsentPurpose).filter_by(code=payload.code).first()
    if existing:
        raise HTTPException(409, f"Purpose code '{payload.code}' already exists")

    purpose = models.ConsentPurpose(
        code=payload.code,
        name=payload.name,
        description=payload.description,
        data_categories=",".join(payload.data_categories),
        source_system=payload.source_system,
        retention_period_days=payload.retention_period_days,
    )
    db.add(purpose)
    db.commit()
    db.refresh(purpose)
    return purpose


@router.get("", response_model=list[schemas.PurposeOut])
def list_purposes(db: Session = Depends(get_db)):
    return db.query(models.ConsentPurpose).order_by(models.ConsentPurpose.created_at.desc()).all()


@router.get("/{purpose_id}", response_model=schemas.PurposeOut)
def get_purpose(purpose_id: str, db: Session = Depends(get_db)):
    purpose = db.get(models.ConsentPurpose, purpose_id)
    if not purpose:
        raise HTTPException(404, "Purpose not found")
    return purpose
