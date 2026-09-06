"""openg2p-sync: manually-triggerable or scheduled push of confirmed-eligible
beneficiaries into a separately-deployed OpenG2P instance.

Deliberately not a live/real-time link: OpenG2P keeps its own local copy of
beneficiary data so program enrollment and disbursement can keep working
through connectivity gaps, per standard G2P deployment practice. This
service owns the *sync event*, not the source of truth.
"""

import os
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

OPENG2P_BASE_URL = os.getenv("OPENG2P_BASE_URL", "http://localhost:8082")
OPENG2P_API_KEY = os.getenv("OPENG2P_API_KEY", "")
OPENG2P_SYNC_MODE = os.getenv("OPENG2P_SYNC_MODE", "manual")
OPENG2P_SYNC_CRON = os.getenv("OPENG2P_SYNC_CRON", "0 */6 * * *")

app = FastAPI(
    title="OpenG2P Sync Service",
    description="Manual/periodic sync of confirmed-eligible beneficiaries into OpenG2P.",
    version="0.1.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class TriggerType(str, Enum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class BeneficiaryRecord(BaseModel):
    golden_record_id: str
    scheme_code: str
    attributes: Dict[str, str]


class SyncTriggerRequest(BaseModel):
    beneficiaries: List[BeneficiaryRecord]
    triggered_by: str = "operator"


class SyncRun(BaseModel):
    id: str
    trigger_type: TriggerType
    triggered_by: str
    status: RunStatus
    beneficiaries_submitted: int
    beneficiaries_synced: int = 0
    error: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None


_runs: List[SyncRun] = []


@app.post("/sync/trigger", response_model=SyncRun, status_code=202)
def trigger_sync(payload: SyncTriggerRequest):
    run = SyncRun(
        id=str(uuid.uuid4()),
        trigger_type=TriggerType.MANUAL,
        triggered_by=payload.triggered_by,
        status=RunStatus.RUNNING,
        beneficiaries_submitted=len(payload.beneficiaries),
        started_at=datetime.now(timezone.utc),
    )
    _runs.append(run)

    try:
        headers = {"Authorization": f"Bearer {OPENG2P_API_KEY}"} if OPENG2P_API_KEY else {}
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                f"{OPENG2P_BASE_URL}/api/beneficiaries/bulk",
                json=[b.model_dump() for b in payload.beneficiaries],
                headers=headers,
            )
            resp.raise_for_status()
        run.beneficiaries_synced = len(payload.beneficiaries)
        run.status = RunStatus.SUCCEEDED
    except httpx.HTTPError as exc:
        run.status = RunStatus.FAILED
        run.error = f"OpenG2P unreachable or rejected the batch: {exc}"

    run.completed_at = datetime.now(timezone.utc)
    return run


@app.get("/sync/runs", response_model=List[SyncRun])
def list_runs():
    return list(reversed(_runs))


@app.get("/sync/runs/{run_id}", response_model=SyncRun)
def get_run(run_id: str):
    run = next((r for r in _runs if r.id == run_id), None)
    if not run:
        raise HTTPException(404, "Sync run not found")
    return run


@app.get("/sync/schedule")
def get_schedule():
    return {"mode": OPENG2P_SYNC_MODE, "cron": OPENG2P_SYNC_CRON, "target": OPENG2P_BASE_URL}


@app.get("/health")
def health():
    """See sunbird-adapter's health handler for why this probes the
    downstream DPG rather than just reporting this service's own liveness."""
    downstream_reachable = False
    try:
        with httpx.Client(timeout=2.0) as client:
            client.get(OPENG2P_BASE_URL)
        downstream_reachable = True
    except httpx.HTTPError:
        pass
    return {
        "status": "ok",
        "service": "openg2p-sync",
        "downstream": {"name": "OpenG2P", "reachable": downstream_reachable},
    }
