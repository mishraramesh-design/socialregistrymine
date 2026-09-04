import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ConsentStatus(str, enum.Enum):
    GRANTED = "granted"
    REVOKED = "revoked"
    EXPIRED = "expired"


class CollectionChannel(str, enum.Enum):
    WEB = "web"
    MOBILE_APP = "mobile_app"
    CSC = "csc_center"
    FIELD_AGENT = "field_agent"
    API = "api"


class ConsentPurpose(Base):
    """A registered reason data may be collected/shared — the DPDP 'notice' content
    an operator configures once per data-sharing use case (e.g. 'Ration DB -> Registry
    matching', 'Registry -> Scheme X eligibility check')."""

    __tablename__ = "consent_purposes"

    id = Column(String, primary_key=True, default=_uuid)
    code = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    data_categories = Column(Text, nullable=False)  # comma-separated for simplicity
    source_system = Column(String, nullable=True)
    retention_period_days = Column(Integer, nullable=False, default=365)
    created_at = Column(DateTime, default=_now)

    consents = relationship("ConsentRecord", back_populates="purpose")


class ConsentRecord(Base):
    """A single data principal's (citizen's) consent grant/revocation for one purpose."""

    __tablename__ = "consent_records"

    id = Column(String, primary_key=True, default=_uuid)
    data_principal_id = Column(String, nullable=False, index=True)
    purpose_id = Column(String, ForeignKey("consent_purposes.id"), nullable=False)
    status = Column(Enum(ConsentStatus), nullable=False, default=ConsentStatus.GRANTED)
    collection_channel = Column(Enum(CollectionChannel), nullable=False)
    granted_by = Column(String, nullable=False)  # self / guardian / field_agent:<id>
    consent_artifact_version = Column(String, nullable=False, default="v1")
    granted_at = Column(DateTime, default=_now)
    expires_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    revocation_reason = Column(Text, nullable=True)

    purpose = relationship("ConsentPurpose", back_populates="consents")
    audit_entries = relationship("ConsentAuditLog", back_populates="consent", order_by="ConsentAuditLog.timestamp")


class ConsentAuditLog(Base):
    """Immutable trail of every action taken on a consent record — required for
    DPDP-style accountability (who accessed/changed what, and why)."""

    __tablename__ = "consent_audit_log"

    id = Column(String, primary_key=True, default=_uuid)
    consent_id = Column(String, ForeignKey("consent_records.id"), nullable=False)
    action = Column(String, nullable=False)  # created / revoked / accessed / renewed
    actor = Column(String, nullable=False)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=_now)

    consent = relationship("ConsentRecord", back_populates="audit_entries")
