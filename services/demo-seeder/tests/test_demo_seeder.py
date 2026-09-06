import os
import subprocess
import sys
import time

import httpx
import pytest
from fastapi.testclient import TestClient

FAKE_GATEWAY_PORT = 8681
os.environ["API_BASE_URL"] = f"http://127.0.0.1:{FAKE_GATEWAY_PORT}"

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.main import app, state  # noqa: E402  (must follow the env var + path setup above)

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_state():
    state.reset()
    yield
    state.reset()


@pytest.fixture(scope="module", autouse=True)
def fake_gateway_server():
    """Runs a minimal fake api-gateway as a real subprocess — demo-seeder
    talks to it over real HTTP, same as it would talk to the real gateway."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "fake_gateway:app", "--host", "127.0.0.1", "--port", str(FAKE_GATEWAY_PORT)],
        cwd=os.path.dirname(__file__),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(50):
        try:
            httpx.post(f"http://127.0.0.1:{FAKE_GATEWAY_PORT}/api/consent/purposes", timeout=0.5)
            break
        except httpx.HTTPError:
            time.sleep(0.2)
    yield
    proc.terminate()
    proc.wait(timeout=5)


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_status_starts_idle():
    assert client.get("/status").json()["status"] == "idle"


def test_seed_rejects_concurrent_start():
    first = client.post("/seed")
    assert first.status_code == 200
    assert first.json()["status"] == "started"

    # The fake gateway's first call sleeps 2s, so this lands mid-run.
    second = client.post("/seed")
    assert second.status_code == 409


def test_seed_reports_failure_when_gateway_unreachable(monkeypatch):
    monkeypatch.setenv("API_BASE_URL", "http://127.0.0.1:1")  # nothing listens here
    import app.main as m

    monkeypatch.setattr(m, "API_BASE_URL", "http://127.0.0.1:1")

    resp = client.post("/seed")
    assert resp.status_code == 200

    deadline = time.time() + 10
    status = client.get("/status").json()
    while status["status"] == "running" and time.time() < deadline:
        time.sleep(0.2)
        status = client.get("/status").json()

    assert status["status"] == "failed"
    assert status["error"]
