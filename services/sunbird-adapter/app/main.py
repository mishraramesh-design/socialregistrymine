"""sunbird-adapter: the only service that talks to a separately-deployed
Sunbird RC instance.

Keeping this as its own thin service (rather than calling Sunbird RC directly
from registry-intelligence) means the registry backend can be swapped without
touching matching/classification logic — e.g. for a client that mandates a
different DPG or an in-house store.
"""

import os
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

SUNBIRD_RC_BASE_URL = os.getenv("SUNBIRD_RC_BASE_URL", "http://localhost:8081")
SUNBIRD_RC_API_KEY = os.getenv("SUNBIRD_RC_API_KEY", "")

app = FastAPI(
    title="Sunbird RC Adapter",
    description="Pushes confirmed golden records to Sunbird RC and tracks registration status.",
    version="0.1.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class PushStatus(str, Enum):
    PENDING = "pending"
    REGISTERED = "registered"
    FAILED = "failed"


class GoldenRecordPush(BaseModel):
    golden_record_id: str
    attributes: Dict[str, str]


class RegistrationRecord(BaseModel):
    golden_record_id: str
    sunbird_rc_entity_id: Optional[str] = None
    status: PushStatus
    error: Optional[str] = None
    pushed_at: datetime


_registrations: Dict[str, RegistrationRecord] = {}


@app.post("/golden-records/{golden_record_id}/push", response_model=RegistrationRecord, status_code=201)
def push_golden_record(golden_record_id: str, payload: GoldenRecordPush):
    if golden_record_id != payload.golden_record_id:
        raise HTTPException(422, "Path golden_record_id must match payload")

    now = datetime.now(timezone.utc)
    try:
        headers = {"Authorization": f"Bearer {SUNBIRD_RC_API_KEY}"} if SUNBIRD_RC_API_KEY else {}
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                f"{SUNBIRD_RC_BASE_URL}/api/v1/Citizen",
                json=payload.attributes,
                headers=headers,
            )
            resp.raise_for_status()
            entity_id = resp.json().get("result", {}).get("Citizen", {}).get("osid", str(uuid.uuid4()))
        record = RegistrationRecord(
            golden_record_id=golden_record_id,
            sunbird_rc_entity_id=entity_id,
            status=PushStatus.REGISTERED,
            pushed_at=now,
        )
    except httpx.HTTPError as exc:
        record = RegistrationRecord(
            golden_record_id=golden_record_id,
            status=PushStatus.FAILED,
            error=f"Sunbird RC unreachable or rejected the record: {exc}",
            pushed_at=now,
        )

    _registrations[golden_record_id] = record
    return record


@app.get("/golden-records/{golden_record_id}/status", response_model=RegistrationRecord)
def get_status(golden_record_id: str):
    record = _registrations.get(golden_record_id)
    if not record:
        raise HTTPException(404, "No registration attempt found for this golden record")
    return record


@app.get("/health")
def health():
    return {"status": "ok", "service": "sunbird-adapter"}
