import os
import sys

os.environ["OPENG2P_BASE_URL"] = "http://127.0.0.1:1"  # nothing listens here

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.main import app  # noqa: E402  (must follow the env var + path setup above)

from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_reports_downstream_unreachable():
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["downstream"]["reachable"] is False


def test_sync_schedule():
    resp = client.get("/sync/schedule").json()
    assert resp["target"] == "http://127.0.0.1:1"


def test_trigger_sync_fails_gracefully_when_openg2p_unreachable():
    resp = client.post("/sync/trigger", json={"beneficiaries": [], "triggered_by": "tester"})
    assert resp.status_code == 202
    run = resp.json()
    assert run["status"] == "failed"
    assert run["error"]

    listed = client.get("/sync/runs").json()
    assert listed[0]["id"] == run["id"]  # newest first
