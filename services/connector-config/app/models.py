import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Connector(Base):
    __tablename__ = "connectors"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String, nullable=False)
    source_type = Column(String, nullable=False)
    department = Column(String, nullable=False)
    connection_config = Column(JSON, nullable=False, default=dict)
    schema_mapping = Column(JSON, nullable=False, default=dict)
    refresh_mode = Column(String, nullable=False)
    refresh_cron = Column(String, nullable=True)
    consent_purpose_code = Column(String, nullable=False)
    status = Column(String, nullable=False, default="draft")
    created_at = Column(DateTime, default=_now)

    runs = relationship("IngestionRun", back_populates="connector", order_by="IngestionRun.started_at")


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id = Column(String, primary_key=True, default=_uuid)
    connector_id = Column(String, ForeignKey("connectors.id"), nullable=False)
    triggered_by = Column(String, nullable=False)
    status = Column(String, nullable=False, default="queued")
    records_seen = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime, default=_now)
    completed_at = Column(DateTime, nullable=True)

    connector = relationship("Connector", back_populates="runs")
