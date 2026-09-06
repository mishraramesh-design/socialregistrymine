import os
import subprocess
import sys
import time

import httpx
import pytest

FAKE_BACKENDS_PORT = 8681
BASE = f"http://127.0.0.1:{FAKE_BACKENDS_PORT}"

os.environ["CONSENT_SERVICE_URL"] = f"{BASE}/consent"
os.environ["CONNECTOR_SERVICE_URL"] = f"{BASE}/connectors"
os.environ["REGISTRY_SERVICE_URL"] = f"{BASE}/registry"
os.environ["DELIVERY_SERVICE_URL"] = f"{BASE}/delivery"
os.environ["SUNBIRD_ADAPTER_SERVICE_URL"] = f"{BASE}/sunbird"
os.environ["DIGIT_ADAPTER_SERVICE_URL"] = f"{BASE}/digit"
os.environ["OPENG2P_SYNC_SERVICE_URL"] = f"{BASE}/openg2p"

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.main import app  # noqa: E402  (must follow the env var + path setup above)

from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def fake_backends_server():
    """Runs fake_backends.py as a real subprocess (not an in-process import)
    — api-gateway's aggregator makes real HTTP calls, not ASGI-transport
    calls, so this exercises the same code path production traffic does."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "fake_backends:app", "--host", "127.0.0.1", "--port", str(FAKE_BACKENDS_PORT)],
        cwd=os.path.dirname(__file__),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(50):
        try:
            httpx.get(f"{BASE}/consent/health", timeout=0.5)
            break
        except httpx.HTTPError:
            time.sleep(0.2)
    yield
    proc.terminate()
    proc.wait(timeout=5)


def test_bare_health_and_api_health_both_work():
    for path in ("/health", "/api/health"):
        resp = client.get(path)
        assert resp.status_code == 200
        body = resp.json()
        assert body["gateway"] == "ok"
        assert body["services"]["consent"]["status"] == "ok"
        # inji/demo aren't faked here — they default to unresolvable Docker
        # hostnames in this environment, which must degrade, not crash.
        assert body["services"]["inji"]["status"] == "unreachable"


def test_audit_timeline_aggregates_every_service():
    resp = client.get("/api/audit/timeline")
    assert resp.status_code == 200
    events = resp.json()

    actions = {e["action"] for e in events}
    assert actions == {
        "consent_granted", "consent_revoked", "ingestion_run", "golden_record_created",
        "doubt_record_flagged", "doubt_record_resolved", "verification_case_opened",
        "digit_routed", "sunbird_pushed", "openg2p_sync",
    }

    # sorted newest-first
    timestamps = [e["timestamp"] for e in events]
    assert timestamps == sorted(timestamps, reverse=True)

    resolved = next(e for e in events if e["action"] == "doubt_record_resolved")
    assert resolved["actor"] == "reviewer"
    assert "promote_to_new_golden" in resolved["summary"]


def test_audit_timeline_survives_unreachable_service(monkeypatch):
    monkeypatch.setenv("REGISTRY_SERVICE_URL", "http://127.0.0.1:1")  # nothing listens here
    import app.main as m
    monkeypatch.setitem(m.SERVICE_ROUTES, "registry", "http://127.0.0.1:1")

    resp = client.get("/api/audit/timeline")
    assert resp.status_code == 200
    actions = {e["action"] for e in resp.json()}
    assert "golden_record_created" not in actions
    assert "doubt_record_resolved" not in actions
    assert "consent_granted" in actions  # every other service's events still show up
