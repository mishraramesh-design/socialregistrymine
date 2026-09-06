import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient

from app.main import _processes, app

client = TestClient(app)


def setup_function():
    _processes.clear()


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_transition_creates_process_and_search_finds_it():
    resp = client.post(
        "/egov-workflow-v2/egov-wf/process/_transition",
        json={
            "RequestInfo": {"apiId": "x", "authToken": "", "ts": 0},
            "ProcessInstances": [
                {"tenantId": "pilot", "businessId": "REG-1", "businessService": "REGISTRY_VERIFICATION", "action": "CREATE", "comment": "test"}
            ],
        },
    )
    assert resp.status_code == 200
    created = resp.json()["ProcessInstances"][0]
    assert created["businessId"] == "REG-1"
    assert created["state"]["state"] == "PENDING_ASSIGNMENT"

    found = client.post(
        "/egov-workflow-v2/egov-wf/process/_search",
        json={"RequestInfo": {}},
        params={"tenantId": "pilot", "businessIds": "REG-1"},
    ).json()
    assert len(found["ProcessInstances"]) == 1
    assert found["ProcessInstances"][0]["id"] == created["id"]


def test_state_progresses_over_time():
    from app.main import _current_state

    record = {"created_at": __import__("time").time() - 15}  # 15s elapsed
    assert _current_state(record) == "FIELD_VISIT_SCHEDULED"

    record["created_at"] -= 20  # now 35s elapsed total
    assert _current_state(record) == "VERIFIED"


def test_search_for_unknown_business_id_returns_empty():
    resp = client.post(
        "/egov-workflow-v2/egov-wf/process/_search",
        json={"RequestInfo": {}},
        params={"tenantId": "pilot", "businessIds": "NOT-A-REAL-ID"},
    )
    assert resp.json()["ProcessInstances"] == []
