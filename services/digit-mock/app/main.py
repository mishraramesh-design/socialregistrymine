"""digit-mock: a lightweight stand-in for DIGIT's egov-workflow-v2 API.

This is NOT a substitute for real DIGIT — DIGIT is a large, Kubernetes-first
platform (see deploy/README.md for why we didn't stand up a real cluster for
this POC). What this mock does is implement the exact two endpoints
`digit-adapter` actually calls (`/process/_transition`, `/process/_search`),
using DIGIT's real request/response shape (RequestInfo envelope,
ProcessInstances array), so the verification-routing story in the POC —
"a doubt record gets sent for field verification, and later comes back
resolved" — demos end-to-end without requiring a real cluster.

Each routed case auto-progresses through realistic states over time (see
_STATE_TIMELINE) purely so a demo that checks status twice, a bit apart,
sees it move — this is illustrative, not a workflow engine.
"""

import time
import uuid
from typing import Dict, List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(
    title="DIGIT Mock (egov-workflow-v2 stand-in)",
    description="Implements the exact API shape digit-adapter calls, for demoing "
    "verification routing without a real Kubernetes-deployed DIGIT.",
    version="0.1.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# (seconds since creation, state) — state at time T is the last entry whose
# threshold has passed. Ends at a terminal state so repeated polls stabilize.
_STATE_TIMELINE = [
    (0, "PENDING_ASSIGNMENT"),
    (10, "FIELD_VISIT_SCHEDULED"),
    (25, "VERIFIED"),
]


class ProcessInstance(BaseModel):
    tenantId: str
    businessId: str
    businessService: str
    action: str
    comment: Optional[str] = None
    moduleName: Optional[str] = None


class TransitionRequest(BaseModel):
    RequestInfo: dict
    ProcessInstances: List[ProcessInstance]


_processes: Dict[str, dict] = {}  # businessId -> record


def _current_state(record: dict) -> str:
    elapsed = time.time() - record["created_at"]
    state = _STATE_TIMELINE[0][1]
    for threshold, s in _STATE_TIMELINE:
        if elapsed >= threshold:
            state = s
    return state


@app.post("/egov-workflow-v2/egov-wf/process/_transition")
def transition(payload: TransitionRequest):
    results = []
    for pi in payload.ProcessInstances:
        record = _processes.get(pi.businessId)
        if not record:
            record = {
                "id": str(uuid.uuid4()),
                "tenantId": pi.tenantId,
                "businessId": pi.businessId,
                "businessService": pi.businessService,
                "created_at": time.time(),
            }
            _processes[pi.businessId] = record
        results.append(
            {
                "id": record["id"],
                "tenantId": record["tenantId"],
                "businessId": record["businessId"],
                "businessService": record["businessService"],
                "state": {"state": _current_state(record)},
            }
        )
    return {"ProcessInstances": results}


@app.post("/egov-workflow-v2/egov-wf/process/_search")
def search(payload: dict, tenantId: str = "", businessIds: str = ""):
    ids = [b for b in businessIds.split(",") if b]
    matches = []
    for business_id in ids:
        record = _processes.get(business_id)
        if record:
            matches.append(
                {
                    "id": record["id"],
                    "tenantId": record["tenantId"],
                    "businessId": record["businessId"],
                    "businessService": record["businessService"],
                    "state": {"state": _current_state(record)},
                }
            )
    return {"ProcessInstances": matches}


@app.get("/health")
def health():
    return {"status": "ok", "service": "digit-mock"}
