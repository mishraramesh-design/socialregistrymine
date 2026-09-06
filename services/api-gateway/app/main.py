"""api-gateway: single entry point for the frontend (and any external caller).

Routes /api/<service>/* to the matching backend microservice over its internal
URL, and — when GATEWAY_API_KEY is set — requires it on every proxied call via
an `X-API-Key` header. Auth is off by default (empty key = no check) so local
dev stays frictionless; a real deployment must set GATEWAY_API_KEY. This is a
shared-secret gate, not per-user auth — SSO/RBAC in front of this is a later
step for a real multi-user deployment, not implemented here.
"""

import asyncio
import os
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

app = FastAPI(title="API Gateway", version="0.3.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

GATEWAY_API_KEY = os.getenv("GATEWAY_API_KEY", "")

SERVICE_ROUTES = {
    "consent": os.getenv("CONSENT_SERVICE_URL", "http://consent-management:8001"),
    "connectors": os.getenv("CONNECTOR_SERVICE_URL", "http://connector-config:8002"),
    "registry": os.getenv("REGISTRY_SERVICE_URL", "http://registry-intelligence:8003"),
    "delivery": os.getenv("DELIVERY_SERVICE_URL", "http://delivery-intelligence:8004"),
    "openg2p-sync": os.getenv("OPENG2P_SYNC_SERVICE_URL", "http://openg2p-sync:8005"),
    "sunbird": os.getenv("SUNBIRD_ADAPTER_SERVICE_URL", "http://sunbird-adapter:8006"),
    "digit": os.getenv("DIGIT_ADAPTER_SERVICE_URL", "http://digit-adapter:8007"),
    "inji": os.getenv("INJI_ADAPTER_SERVICE_URL", "http://inji-adapter:8008"),
    "demo": os.getenv("DEMO_SEEDER_SERVICE_URL", "http://demo-seeder:8009"),
}


def _check_api_key(x_api_key: str = Header(default="")):
    if not GATEWAY_API_KEY:
        return  # auth disabled — no key configured
    if not secrets.compare_digest(x_api_key, GATEWAY_API_KEY):
        raise HTTPException(401, "Missing or invalid X-API-Key")


async def _aggregate_health() -> dict:
    results = {}
    async with httpx.AsyncClient(timeout=3.0) as client:
        for name, base_url in SERVICE_ROUTES.items():
            try:
                resp = await client.get(f"{base_url}/health")
                results[name] = resp.json()
            except httpx.HTTPError:
                results[name] = {"status": "unreachable"}
    return {"gateway": "ok", "services": results}


@app.get("/health")
async def health():
    """Aggregate health check — pings every downstream service. Not behind the
    API key gate: it reveals only service-up/down status, useful for infra
    monitoring that shouldn't need the application key. Registered bare (for
    direct/infra callers) — see /api/health below for why the frontend can't
    use this path directly."""
    return await _aggregate_health()


@app.get("/api/health")
async def health_via_api_prefix():
    """Same as /health, reachable through nginx's /api/ proxy. nginx forwards
    the full incoming path unchanged (see frontend/nginx.conf), so a request
    the frontend makes to a bare /health never reaches this service in
    production — it falls through nginx's SPA catch-all and gets index.html
    back instead. This alias is what the frontend actually calls."""
    return await _aggregate_health()


class AuditEvent(BaseModel):
    timestamp: datetime
    service: str
    action: str
    actor: Optional[str] = None
    summary: str
    detail: Dict[str, Any] = {}

    @field_validator("timestamp")
    @classmethod
    def _assume_utc_if_naive(cls, v: datetime) -> datetime:
        """Every service's own timestamps are generated as UTC, but SQLite
        round-trips through SQLAlchemy drop tzinfo on the way back out (the
        in-memory adapters' Pydantic models don't) — so the same timeline
        mixes naive and aware datetimes, which sort() can't compare across.
        Normalize by treating a naive value as UTC (correct here — nothing
        in this codebase generates naive local time)."""
        return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v


async def _safe_get(client: httpx.AsyncClient, url: str, params: Optional[dict] = None) -> Optional[Any]:
    """Every audit source is best-effort: a downstream service being down or
    slow should drop that service's events from the timeline, not break the
    whole page."""
    try:
        resp = await client.get(url, params=params, timeout=10.0)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError:
        return None


async def _consent_events(client: httpx.AsyncClient) -> List[AuditEvent]:
    consents = await _safe_get(client, f"{SERVICE_ROUTES['consent']}/consents")
    events: List[AuditEvent] = []
    for c in consents or []:
        events.append(AuditEvent(
            timestamp=c["granted_at"], service="consent", action="consent_granted", actor=c.get("granted_by"),
            summary=f"Consent granted — data principal {c['data_principal_id']}, purpose {c['purpose_id']}, via {c['collection_channel']}",
            detail=c,
        ))
        if c.get("revoked_at"):
            reason = f" — {c['revocation_reason']}" if c.get("revocation_reason") else ""
            events.append(AuditEvent(
                timestamp=c["revoked_at"], service="consent", action="consent_revoked",
                summary=f"Consent revoked — data principal {c['data_principal_id']}{reason}",
                detail=c,
            ))
    return events


async def _connector_events(client: httpx.AsyncClient) -> List[AuditEvent]:
    connectors = await _safe_get(client, f"{SERVICE_ROUTES['connectors']}/connectors")
    events: List[AuditEvent] = []
    if not connectors:
        return events
    run_lists = await asyncio.gather(
        *[_safe_get(client, f"{SERVICE_ROUTES['connectors']}/connectors/{c['id']}/runs") for c in connectors]
    )
    for connector, runs in zip(connectors, run_lists):
        for run in runs or []:
            events.append(AuditEvent(
                timestamp=run.get("completed_at") or run["started_at"],
                service="connectors", action="ingestion_run", actor=run.get("triggered_by"),
                summary=(
                    f"{connector['name']}: {run['records_seen']} records -> "
                    f"{run['golden_count']} golden, {run['doubt_count']} doubt, "
                    f"{run['failed_count']} failed ({run['status']})"
                ),
                detail=run,
            ))
    return events


async def _registry_events(client: httpx.AsyncClient) -> List[AuditEvent]:
    events: List[AuditEvent] = []
    golden = await _safe_get(client, f"{SERVICE_ROUTES['registry']}/golden-records")
    for g in golden or []:
        events.append(AuditEvent(
            timestamp=g["created_at"], service="registry", action="golden_record_created",
            summary=f"Golden record created — {g['attributes'].get('name', g['id'])} ({len(g['contributing_sources'])} source(s))",
            detail=g,
        ))
    doubts = await _safe_get(client, f"{SERVICE_ROUTES['registry']}/doubt-records")
    for d in doubts or []:
        events.append(AuditEvent(
            timestamp=d["created_at"], service="registry", action="doubt_record_flagged",
            summary=(
                f"Doubt record flagged — {d['attributes'].get('name', d['id'])} "
                f"({d['classification']}, {len(d['candidate_matches'])} candidate match(es))"
            ),
            detail=d,
        ))
        if d.get("resolved_at"):
            events.append(AuditEvent(
                timestamp=d["resolved_at"], service="registry", action="doubt_record_resolved", actor=d.get("resolved_by"),
                summary=f"Doubt record resolved — {d['attributes'].get('name', d['id'])} ({d.get('resolution')})",
                detail=d,
            ))
    return events


async def _delivery_events(client: httpx.AsyncClient) -> List[AuditEvent]:
    cases = await _safe_get(client, f"{SERVICE_ROUTES['delivery']}/verification-cases")
    events: List[AuditEvent] = []
    for c in cases or []:
        events.append(AuditEvent(
            timestamp=c["created_at"], service="delivery", action="verification_case_opened",
            summary=f"Verification case opened — scheme {c['scheme_code']}: {c['reason']}",
            detail=c,
        ))
    return events


async def _digit_events(client: httpx.AsyncClient) -> List[AuditEvent]:
    routings = await _safe_get(client, f"{SERVICE_ROUTES['digit']}/verification-cases")
    events: List[AuditEvent] = []
    for r in routings or []:
        state = f" (state: {r['digit_state']})" if r.get("digit_state") else ""
        events.append(AuditEvent(
            timestamp=r["routed_at"], service="digit", action="digit_routed",
            summary=f"Verification case {r['verification_case_id']} routed to DIGIT — {r['status']}{state}",
            detail=r,
        ))
    return events


async def _sunbird_events(client: httpx.AsyncClient) -> List[AuditEvent]:
    regs = await _safe_get(client, f"{SERVICE_ROUTES['sunbird']}/golden-records")
    events: List[AuditEvent] = []
    for r in regs or []:
        events.append(AuditEvent(
            timestamp=r["pushed_at"], service="sunbird", action="sunbird_pushed",
            summary=f"Golden record {r['golden_record_id']} pushed to Sunbird RC — {r['status']}",
            detail=r,
        ))
    return events


async def _openg2p_events(client: httpx.AsyncClient) -> List[AuditEvent]:
    runs = await _safe_get(client, f"{SERVICE_ROUTES['openg2p-sync']}/sync/runs")
    events: List[AuditEvent] = []
    for r in runs or []:
        events.append(AuditEvent(
            timestamp=r.get("completed_at") or r["started_at"],
            service="openg2p-sync", action="openg2p_sync", actor=r.get("triggered_by"),
            summary=f"OpenG2P sync — {r['beneficiaries_submitted']} submitted, {r['beneficiaries_synced']} synced ({r['status']})",
            detail=r,
        ))
    return events


@app.get("/api/audit/timeline", response_model=List[AuditEvent])
async def audit_timeline(x_api_key: str = Header(default="")):
    """Aggregates every auditable action across every service into one
    chronological trail — consent grants/revocations, ingestion runs, golden
    record creation, doubt flags/resolutions, verification cases, DIGIT
    routing, Sunbird RC pushes, and OpenG2P syncs. Read-only, best-effort per
    service (see _safe_get): a slow or down service just contributes no
    events rather than failing the whole call."""
    _check_api_key(x_api_key)
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            _consent_events(client),
            _connector_events(client),
            _registry_events(client),
            _delivery_events(client),
            _digit_events(client),
            _sunbird_events(client),
            _openg2p_events(client),
        )
    events: List[AuditEvent] = [event for group in results for event in group]
    events.sort(key=lambda e: e.timestamp, reverse=True)
    return events


@app.api_route("/api/{service}/{path:path}", methods=["GET", "POST", "PATCH", "PUT", "DELETE"])
async def proxy(service: str, path: str, request: Request, x_api_key: str = Header(default="")):
    _check_api_key(x_api_key)

    base_url = SERVICE_ROUTES.get(service)
    if not base_url:
        return Response(content=f'{{"detail": "Unknown service \\"{service}\\""}}', status_code=404, media_type="application/json")

    body = await request.body()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            upstream = await client.request(
                request.method,
                f"{base_url}/{path}",
                params=dict(request.query_params),
                content=body,
                headers={k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length")},
            )
    except httpx.HTTPError as exc:
        return Response(
            content=f'{{"detail": "Service \\"{service}\\" unreachable: {exc}"}}',
            status_code=502,
            media_type="application/json",
        )
    return Response(content=upstream.content, status_code=upstream.status_code, media_type=upstream.headers.get("content-type"))
