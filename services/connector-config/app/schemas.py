from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


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


class ConnectorOut(ConnectorCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: ConnectorStatus
    created_at: datetime


class IngestionRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    connector_id: str
    triggered_by: str
    status: str
    records_seen: int
    golden_count: int
    doubt_count: int
    failed_count: int
    error: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None


class TriggerRunRequest(BaseModel):
    records: Optional[List[Dict[str, str]]] = Field(
        None,
        description="Raw source-side records to ingest, required for database/flat_file connectors "
        "(no live driver exists yet — see README). Ignored for api connectors, which fetch live from "
        "connection_config['url'] instead.",
    )
