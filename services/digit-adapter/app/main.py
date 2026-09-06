"""digit-adapter: routes Doubt-Registry verification cases to a separately-deployed
DIGIT instance's workflow engine for field-agent verification.

DIGIT's workflow service (egov-workflow-v2) uses a BusinessService/process model:
a "process" is created and moved through states via `/process/_transition`, and every
call carries a `RequestInfo` envelope (eGov's standard auth/request-metadata wrapper)
rather than a plain bearer token in the body. Endpoint paths below are the real,
documented egov-workflow-v2 paths — verified against DIGIT's own API docs, not
guessed. What's NOT pinned here, because it's specific to how DIGIT is configured
for this deployment: the BusinessService code (e.g. "REGISTRY_VERIFICATION") must
be created in DIGIT first (see DIGIT's workflow setup guide) — set it via
DIGIT_BUSINESS_SERVICE — and DIGIT_AUTH_TOKEN must come from DIGIT's own
`/user/oauth/token` employee-login endpoint (not implemented here — that's an
operational credential, not something this adapter should mint).
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

DIGIT_BASE_URL = os.getenv("DIGIT_BASE_URL", "http://localhost:8083")
DIGIT_AUTH_TOKEN = os.getenv("DIGIT_AUTH_TOKEN", "")
DIGIT_TENANT_ID = os.getenv("DIGIT_TENANT_ID", "pilot")
DIGIT_BUSINESS_SERVICE = os.getenv("DIGIT_BUSINESS_SERVICE", "REGISTRY_VERIFICATION")

app = FastAPI(
    title="DIGIT Adapter",
    description="Routes Doubt Registry verification cases to DIGIT's workflow engine for field verification.",
    version="0.1.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class RouteStatus(str, Enum):
    PENDING = "pending"
    ROUTED = "routed"
    FAILED = "failed"


class RouteCaseRequest(BaseModel):
    verification_case_id: str
    doubt_record_id: str
    reason: str


class RoutingRecord(BaseModel):
    verification_case_id: str
    digit_process_instance_id: Optional[str] = None
    status: RouteStatus
    digit_state: Optional[str] = None
    error: Optional[str] = None
    routed_at: datetime


_routings: Dict[str, RoutingRecord] = {}


def _request_info() -> dict:
    """eGov's standard request envelope — every DIGIT API call carries this."""
    return {
        "apiId": "socialregistrymine.digit-adapter",
        "authToken": DIGIT_AUTH_TOKEN,
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
    }


@app.post("/verification-cases/{case_id}/route", response_model=RoutingRecord, status_code=201)
def route_case(case_id: str, payload: RouteCaseRequest):
    now = datetime.now(timezone.utc)
    business_id = f"REG-{case_id}"

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                f"{DIGIT_BASE_URL}/egov-workflow-v2/egov-wf/process/_transition",
                json={
                    "RequestInfo": _request_info(),
                    "ProcessInstances": [
                        {
                            "tenantId": DIGIT_TENANT_ID,
                            "businessId": business_id,
                            "businessService": DIGIT_BUSINESS_SERVICE,
                            "action": "CREATE",
                            "comment": payload.reason,
                            "moduleName": "registry-verification",
                        }
                    ],
                },
            )
            resp.raise_for_status()
            process_instance_id = (
                resp.json().get("ProcessInstances", [{}])[0].get("id", str(uuid.uuid4()))
            )
        record = RoutingRecord(
            verification_case_id=case_id,
            digit_process_instance_id=process_instance_id,
            status=RouteStatus.ROUTED,
            routed_at=now,
        )
    except httpx.HTTPError as exc:
        record = RoutingRecord(
            verification_case_id=case_id,
            status=RouteStatus.FAILED,
            error=f"DIGIT unreachable or rejected the case: {exc}",
            routed_at=now,
        )

    _routings[case_id] = record
    return record


@app.get("/verification-cases", response_model=list[RoutingRecord])
def list_routings():
    """Every routing attempt this instance has made, newest first — used by
    api-gateway's /audit/timeline aggregation. In-memory, like the rest of
    this adapter's state (see module docstring): a run/registration log, not
    registry data, so it resets on restart."""
    return sorted(_routings.values(), key=lambda r: r.routed_at, reverse=True)


@app.get("/verification-cases/{case_id}/status", response_model=RoutingRecord)
def get_case_status(case_id: str):
    record = _routings.get(case_id)
    if not record:
        raise HTTPException(404, "No routing attempt found for this verification case")

    if record.status == RouteStatus.ROUTED:
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(
                    f"{DIGIT_BASE_URL}/egov-workflow-v2/egov-wf/process/_search",
                    json={"RequestInfo": _request_info()},
                    params={"tenantId": DIGIT_TENANT_ID, "businessIds": f"REG-{case_id}"},
                )
                resp.raise_for_status()
                instances = resp.json().get("ProcessInstances", [])
                if instances:
                    record.digit_state = instances[0].get("state", {}).get("state")
                    _routings[case_id] = record
        except httpx.HTTPError:
            pass  # keep the last-known routing record if DIGIT is unreachable right now

    return record


@app.get("/health")
def health():
    """See sunbird-adapter's health handler for why this probes the
    downstream DPG rather than just reporting the adapter's own liveness."""
    downstream_reachable = False
    try:
        with httpx.Client(timeout=2.0) as client:
            client.get(DIGIT_BASE_URL)
        downstream_reachable = True
    except httpx.HTTPError:
        pass
    return {
        "status": "ok",
        "service": "digit-adapter",
        "downstream": {"name": "DIGIT", "reachable": downstream_reachable},
    }
