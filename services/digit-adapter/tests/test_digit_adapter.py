import os
import subprocess
import sys
import time

import httpx
import pytest
from fastapi.testclient import TestClient

DIGIT_MOCK_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../digit-mock"))
DIGIT_MOCK_PORT = 8583

os.environ["DIGIT_BASE_URL"] = f"http://127.0.0.1:{DIGIT_MOCK_PORT}"

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.main import app  # noqa: E402  (must follow the env var + path setup above)

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def digit_mock_server():
    """Runs digit-mock as a real subprocess (not an in-process import) — both
    services have a module named `app.main`, which would collide in a single
    interpreter's sys.modules if imported directly."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(DIGIT_MOCK_PORT)],
        cwd=DIGIT_MOCK_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(50):
        try:
            httpx.get(f"http://127.0.0.1:{DIGIT_MOCK_PORT}/health", timeout=0.5)
            break
        except httpx.HTTPError:
            time.sleep(0.2)
    yield
    proc.terminate()
    proc.wait(timeout=5)


def test_health():
    body = client.get("/health").json()
    assert body["status"] == "ok"
    # digit_mock_server (module fixture) is already up by this point, so the
    # adapter should honestly report the downstream DPG as reachable.
    assert body["downstream"]["reachable"] is True


def test_status_for_unknown_case_is_404():
    resp = client.get("/verification-cases/does-not-exist/status")
    assert resp.status_code == 404


def test_route_case_and_check_status_against_real_digit_mock():
    resp = client.post(
        "/verification-cases/case-1/route",
        json={"verification_case_id": "case-1", "doubt_record_id": "doubt-1", "reason": "no shared identifier"},
    )
    assert resp.status_code == 201
    routed = resp.json()
    assert routed["status"] == "routed"
    assert routed["digit_process_instance_id"]

    status = client.get("/verification-cases/case-1/status").json()
    assert status["status"] == "routed"
    assert status["digit_state"] == "PENDING_ASSIGNMENT"


def test_list_routings_includes_routed_case():
    case_ids = [r["verification_case_id"] for r in client.get("/verification-cases").json()]
    assert "case-1" in case_ids
