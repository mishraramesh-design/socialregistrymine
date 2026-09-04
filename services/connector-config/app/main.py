"""connector-config: no-code source onboarding.

Registering a new government database or API as a source is a config
operation here, not a new integration project — the payload below is
everything a generic ingestion engine needs to pull from it and map it
onto the canonical citizen/family schema.

Storage is in-memory for this scaffold phase (state is lost on restart);
swap `_connectors` / `_runs` for a persistent store (same SQLAlchemy
pattern as `consent-management`) when this moves past the pilot.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(
    title="Connector Config Service",
    description="No-code registration of source databases/APIs and their mapping "
    "to the canonical citizen/family schema.",
    version="0.1.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class SourceType(str, Enum):
    DATABASE = "database"
    API = "api"
    FLAT_FILE = "flat_file"


class RefreshMode(str, Enum):
    ONE_TIME_BULK = "one_time_bulk"
    SCHEDULED_BATCH = "scheduled_batch"
    EVENT_DRIVEN = "event_driven"


class ConnectorStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"


class ConnectorCreate(BaseModel):
    name: str = Field(..., examples=["Delhi Food & Civil Supply - Ration DB"])
    source_type: SourceType
    department: str
    connection_config: Dict[str, str] = Field(
        ..., description="Connection details — JDBC URL/API endpoint/file path plus auth reference (never the raw secret)."
    )
    schema_mapping: Dict[str, str] = Field(
        ..., description="source_field -> canonical_field, e.g. {'ration_holder_name': 'name', 'dob': 'date_of_birth'}"
    )
    refresh_mode: RefreshMode
    refresh_cron: Optional[str] = Field(None, description="Required when refresh_mode=scheduled_batch")
    consent_purpose_code: str = Field(..., description="Purpose code registered in consent-management for this source")


class Connector(ConnectorCreate):
    id: str
    status: ConnectorStatus = ConnectorStatus.DRAFT
    created_at: datetime


class IngestionRun(BaseModel):
    id: str
    connector_id: str
    triggered_by: str
    status: str
    records_seen: int = 0
    started_at: datetime
    completed_at: Optional[datetime] = None


_connectors: Dict[str, Connector] = {}
_runs: Dict[str, List[IngestionRun]] = {}


@app.post("/connectors", response_model=Connector, status_code=201)
def create_connector(payload: ConnectorCreate):
    if payload.refresh_mode == RefreshMode.SCHEDULED_BATCH and not payload.refresh_cron:
        raise HTTPException(422, "refresh_cron is required when refresh_mode=scheduled_batch")

    connector = Connector(id=str(uuid.uuid4()), created_at=datetime.now(timezone.utc), **payload.model_dump())
    _connectors[connector.id] = connector
    _runs[connector.id] = []
    return connector


@app.get("/connectors", response_model=List[Connector])
def list_connectors():
    return list(_connectors.values())


@app.get("/connectors/{connector_id}", response_model=Connector)
def get_connector(connector_id: str):
    connector = _connectors.get(connector_id)
    if not connector:
        raise HTTPException(404, "Connector not found")
    return connector


@app.patch("/connectors/{connector_id}/status", response_model=Connector)
def set_connector_status(connector_id: str, status: ConnectorStatus):
    connector = _connectors.get(connector_id)
    if not connector:
        raise HTTPException(404, "Connector not found")
    connector.status = status
    return connector


@app.post("/connectors/{connector_id}/trigger-run", response_model=IngestionRun, status_code=202)
def trigger_run(connector_id: str, triggered_by: str = "operator"):
    """Kicks off an ingestion run for this source. In this scaffold it only records
    the run's intent — the actual extract/standardize/match pipeline is owned by
    registry-intelligence, which this endpoint would call in the next build phase."""
    connector = _connectors.get(connector_id)
    if not connector:
        raise HTTPException(404, "Connector not found")
    run = IngestionRun(
        id=str(uuid.uuid4()),
        connector_id=connector_id,
        triggered_by=triggered_by,
        status="queued",
        started_at=datetime.now(timezone.utc),
    )
    _runs[connector_id].append(run)
    return run


@app.get("/connectors/{connector_id}/runs", response_model=List[IngestionRun])
def list_runs(connector_id: str):
    if connector_id not in _runs:
        raise HTTPException(404, "Connector not found")
    return _runs[connector_id]


@app.get("/health")
def health():
    return {"status": "ok", "service": "connector-config"}
