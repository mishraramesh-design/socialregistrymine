import os
import sys

os.environ["INJI_CERTIFY_BASE_URL"] = "http://127.0.0.1:1"  # nothing listens here
os.environ["INJI_VERIFY_BASE_URL"] = "http://127.0.0.1:1"

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.main import app  # noqa: E402  (must follow the env var + path setup above)

from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_reports_both_downstreams_unreachable():
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["downstream"]["certify"]["reachable"] is False
    assert body["downstream"]["verify"]["reachable"] is False


def test_issue_credential_fails_gracefully_when_certify_unreachable():
    resp = client.post(
        "/golden-records/g1/issue-credential",
        json={"golden_record_id": "g1", "claims": {"name": "Test Person"}},
    )
    assert resp.status_code == 201
    record = resp.json()
    assert record["status"] == "failed"
    assert record["error"]
