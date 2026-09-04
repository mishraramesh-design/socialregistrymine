from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from .models import CollectionChannel, ConsentStatus


class PurposeCreate(BaseModel):
    code: str
    name: str
    description: str
    data_categories: List[str]
    source_system: Optional[str] = None
    retention_period_days: int = 365


class PurposeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    description: str
    data_categories: str
    source_system: Optional[str]
    retention_period_days: int
    created_at: datetime


class ConsentCreate(BaseModel):
    data_principal_id: str
    purpose_code: str
    collection_channel: CollectionChannel
    granted_by: str = "self"
    consent_artifact_version: str = "v1"
    expires_at: Optional[datetime] = None


class ConsentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    data_principal_id: str
    purpose_id: str
    status: ConsentStatus
    collection_channel: CollectionChannel
    granted_by: str
    consent_artifact_version: str
    granted_at: datetime
    expires_at: Optional[datetime]
    revoked_at: Optional[datetime]
    revocation_reason: Optional[str]


class ConsentRevoke(BaseModel):
    reason: str
    actor: str = "data_principal"


class AuditEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    action: str
    actor: str
    details: Optional[str]
    timestamp: datetime
