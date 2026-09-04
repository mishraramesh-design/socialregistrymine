import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, String

from .database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class GoldenRecord(Base):
    __tablename__ = "golden_records"

    id = Column(String, primary_key=True, default=_uuid)
    attributes = Column(JSON, nullable=False, default=dict)
    contributing_sources = Column(JSON, nullable=False, default=list)
    classification = Column(String, nullable=False)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now)


class DoubtRecord(Base):
    __tablename__ = "doubt_records"

    id = Column(String, primary_key=True, default=_uuid)
    attributes = Column(JSON, nullable=False, default=dict)
    contributing_sources = Column(JSON, nullable=False, default=list)
    classification = Column(String, nullable=False)
    candidate_matches = Column(JSON, nullable=False, default=list)
    status = Column(String, nullable=False, default="open")
    created_at = Column(DateTime, default=_now)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String, nullable=True)
    resolution = Column(String, nullable=True)
