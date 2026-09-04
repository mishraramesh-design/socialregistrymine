"""api-gateway: single entry point for the frontend (and any external caller).

Routes /api/<service>/* to the matching backend microservice over its internal
URL, and — when GATEWAY_API_KEY is set — requires it on every proxied call via
an `X-API-Key` header. Auth is off by default (empty key = no check) so local
dev stays frictionless; a real deployment must set GATEWAY_API_KEY. This is a
shared-secret gate, not per-user auth — SSO/RBAC in front of this is a later
step for a real multi-user deployment, not implemented here.
"""

import os
import secrets

import httpx
from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="API Gateway", version="0.2.0")
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
}


def _check_api_key(x_api_key: str = Header(default="")):
    if not GATEWAY_API_KEY:
        return  # auth disabled — no key configured
    if not secrets.compare_digest(x_api_key, GATEWAY_API_KEY):
        raise HTTPException(401, "Missing or invalid X-API-Key")


@app.get("/health")
async def health():
    """Aggregate health check — pings every downstream service. Not behind the
    API key gate: it reveals only service-up/down status, useful for infra
    monitoring that shouldn't need the application key."""
    results = {}
    async with httpx.AsyncClient(timeout=3.0) as client:
        for name, base_url in SERVICE_ROUTES.items():
            try:
                resp = await client.get(f"{base_url}/health")
                results[name] = resp.json()
            except httpx.HTTPError:
                results[name] = {"status": "unreachable"}
    return {"gateway": "ok", "services": results}


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
