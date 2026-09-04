"""api-gateway: single entry point for the frontend (and any external caller).

Routes /api/<service>/* to the matching backend microservice over its internal
URL. This is where a client deployment would also add auth (SSO/API keys) and
rate limiting in front of every service — not implemented in this scaffold.
"""

import os

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="API Gateway", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

SERVICE_ROUTES = {
    "consent": os.getenv("CONSENT_SERVICE_URL", "http://consent-management:8001"),
    "connectors": os.getenv("CONNECTOR_SERVICE_URL", "http://connector-config:8002"),
    "registry": os.getenv("REGISTRY_SERVICE_URL", "http://registry-intelligence:8003"),
    "delivery": os.getenv("DELIVERY_SERVICE_URL", "http://delivery-intelligence:8004"),
    "openg2p-sync": os.getenv("OPENG2P_SYNC_SERVICE_URL", "http://openg2p-sync:8005"),
    "sunbird": os.getenv("SUNBIRD_ADAPTER_SERVICE_URL", "http://sunbird-adapter:8006"),
}


@app.get("/health")
async def health():
    """Aggregate health check — pings every downstream service."""
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
async def proxy(service: str, path: str, request: Request):
    base_url = SERVICE_ROUTES.get(service)
    if not base_url:
        return Response(content=f'{{"detail": "Unknown service \\"{service}\\""}}', status_code=404, media_type="application/json")

    body = await request.body()
    async with httpx.AsyncClient(timeout=15.0) as client:
        upstream = await client.request(
            request.method,
            f"{base_url}/{path}",
            params=dict(request.query_params),
            content=body,
            headers={k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length")},
        )
    return Response(content=upstream.content, status_code=upstream.status_code, media_type=upstream.headers.get("content-type"))
