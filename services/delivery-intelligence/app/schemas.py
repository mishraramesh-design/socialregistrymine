from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ComparisonOp(str, Enum):
    EQ = "eq"
    LT = "lt"
    LTE = "lte"
    GT = "gt"
    GTE = "gte"


class RuleCondition(BaseModel):
    field: str
    op: ComparisonOp
    value: float


class SchemeRuleCreate(BaseModel):
    scheme_code: str
    name: str
    eligibility_conditions: List[RuleCondition] = Field(default_factory=list, description="ALL must pass")
    exclusion_conditions: List[RuleCondition] = Field(default_factory=list, description="ANY match excludes")


class SchemeRuleOut(SchemeRuleCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime


class EligibilityCheckRequest(BaseModel):
    citizen_golden_record_id: Optional[str] = None
    citizen_doubt_record_id: Optional[str] = None
    scheme_code: str
    attributes: Dict[str, float]


class EligibilityResult(BaseModel):
    eligible: bool
    scheme_code: str
    failed_conditions: List[str] = []
    excluded_by: List[str] = []
    verification_case_id: Optional[str] = None


class VerificationCaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    reason: str
    citizen_doubt_record_id: Optional[str]
    scheme_code: str
    status: str
    created_at: datetime
