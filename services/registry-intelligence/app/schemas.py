from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ClassificationLevel(str, Enum):
    UNIQUE_COMPLETE = "L1_unique_complete"
    UNIQUE_INCOMPLETE = "L2_unique_incomplete"
    COMPLETE_NOT_UNIQUE = "L3_complete_not_unique"
    NEITHER = "L4_not_unique_not_complete"


class RecordIngest(BaseModel):
    source_connector_id: str
    source_record_id: str
    attributes: Dict[str, str] = Field(..., description="Canonical-schema fields for this record")


class MatchCandidate(BaseModel):
    golden_record_id: Optional[str] = None
    doubt_record_id: Optional[str] = None
    score: float
    evidence: str


class GoldenRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    attributes: Dict[str, str]
    contributing_sources: List[str]
    classification: ClassificationLevel
    created_at: datetime
    updated_at: datetime


class DoubtRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    attributes: Dict[str, str]
    contributing_sources: List[str]
    classification: ClassificationLevel
    candidate_matches: List[MatchCandidate]
    status: str
    created_at: datetime
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution: Optional[str] = None


class DoubtResolution(BaseModel):
    resolved_by: str
    action: str = Field(..., description="'merge_into_golden' or 'promote_to_new_golden'")
    target_golden_record_id: Optional[str] = Field(None, description="Required when action=merge_into_golden")
    notes: Optional[str] = None


class IngestResult(BaseModel):
    classification: ClassificationLevel
    golden_record_id: Optional[str] = None
    doubt_record_id: Optional[str] = None
    candidate_matches: List[MatchCandidate] = []
