import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, String

from .database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SchemeRule(Base):
    __tablename__ = "scheme_rules"

    id = Column(String, primary_key=True, default=_uuid)
    scheme_code = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    eligibility_conditions = Column(JSON, nullable=False, default=list)
    exclusion_conditions = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, default=_now)


class VerificationCase(Base):
    __tablename__ = "verification_cases"

    id = Column(String, primary_key=True, default=_uuid)
    reason = Column(String, nullable=False)
    citizen_doubt_record_id = Column(String, nullable=True)
    scheme_code = Column(String, nullable=False)
    status = Column(String, nullable=False, default="open")
    created_at = Column(DateTime, default=_now)
