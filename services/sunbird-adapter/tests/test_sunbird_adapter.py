import os
import sys
import time

os.environ["SUNBIRD_RC_BASE_URL"] = "http://127.0.0.1:1"  # nothing listens here

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.main import app  # noqa: E402  (must follow the env var + path setup above)

from fastapi.testclient import TestClient

client = TestClient(app)


def test_health():
    body = client.get("/health").json()
    assert body["status"] == "ok"
    # SUNBIRD_RC_BASE_URL points at nothing (see top of file) — the adapter
    # itself is up, but it should honestly report the downstream DPG as not.
    assert body["downstream"]["reachable"] is False


def test_push_records_failed_status_when_sunbird_rc_unreachable():
    resp = client.post(
        "/golden-records/g1/push",
        json={"golden_record_id": "g1", "attributes": {"name": "Test Person"}},
    )
    assert resp.status_code == 201
    record = resp.json()
    assert record["status"] == "failed"
    assert record["error"]

    status = client.get("/golden-records/g1/status").json()
    assert status["status"] == "failed"


def test_status_for_unknown_record_is_404():
    resp = client.get("/golden-records/does-not-exist/status")
    assert resp.status_code == 404


def test_list_registrations_returns_pushed_records_newest_first():
    client.post("/golden-records/g2/push", json={"golden_record_id": "g2", "attributes": {"name": "A"}})
    time.sleep(0.01)  # guarantee a distinct pushed_at from g2's, for the ordering assertion below
    client.post("/golden-records/g3/push", json={"golden_record_id": "g3", "attributes": {"name": "B"}})

    records = client.get("/golden-records").json()
    ids = [r["golden_record_id"] for r in records]
    assert "g2" in ids and "g3" in ids
    # newest first: g3 was pushed after g2
    assert ids.index("g3") < ids.index("g2")
