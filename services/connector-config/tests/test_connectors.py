import os
import sys
import threading
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ["CONNECTOR_DB_URL"] = "sqlite:///./data/test_connectors.db"
os.environ["REGISTRY_SERVICE_URL"] = "http://127.0.0.1:8503"

import httpx
import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# --- A minimal stand-in for registry-intelligence, run as a REAL server on a
# real port (not TestClient) since connector-config's background task talks
# to REGISTRY_SERVICE_URL over actual HTTP, not the ASGI transport. This tests
# connector-config's own mapping/HTTP-calling/run-tracking logic; registry-
# intelligence's own matching logic has its own test suite already. ---

fake_registry = FastAPI()
received_calls = []


@fake_registry.post("/records/ingest")
def fake_ingest(payload: dict):
    received_calls.append(payload)
    if payload["attributes"].get("name") == "Ambiguous Person":
        return {"classification": "L3_complete_not_unique", "doubt_record_id": "doubt-1", "candidate_matches": []}
    return {"classification": "L1_unique_complete", "golden_record_id": f"golden-{len(received_calls)}", "candidate_matches": []}


@pytest.fixture(scope="module", autouse=True)
def fake_registry_server():
    config = uvicorn.Config(fake_registry, host="127.0.0.1", port=8503, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(50):
        if server.started:
            break
        time.sleep(0.1)
    yield
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(autouse=True)
def clean_db():
    received_calls.clear()
    yield
    db_path = "./data/test_connectors.db"
    if os.path.exists(db_path):
        os.remove(db_path)


def _wait_for_run_completion(connector_id: str, timeout: float = 5.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        runs = client.get(f"/connectors/{connector_id}/runs").json()
        if runs and runs[0]["status"] in ("completed", "failed"):
            return runs[0]
        time.sleep(0.1)
    raise AssertionError("run did not complete in time")


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def _create_flat_file_connector():
    return client.post(
        "/connectors",
        json={
            "name": "Delhi Ration DB",
            "source_type": "flat_file",
            "department": "Food & Civil Supply",
            "connection_config": {},
            "schema_mapping": {"ration_holder_name": "name", "dob": "date_of_birth"},
            "refresh_mode": "one_time_bulk",
            "consent_purpose_code": "ration-to-registry-match",
        },
    ).json()


def test_trigger_run_without_records_fails_for_non_api_source():
    connector = _create_flat_file_connector()
    resp = client.post(f"/connectors/{connector['id']}/trigger-run")
    assert resp.status_code == 422


def test_trigger_run_maps_and_ingests_records_into_registry():
    connector = _create_flat_file_connector()

    resp = client.post(
        f"/connectors/{connector['id']}/trigger-run",
        json={"records": [{"ration_holder_name": "Anita Devi", "dob": "1990-01-01", "unused_field": "ignored"}]},
        params={"triggered_by": "operator1"},
    )
    assert resp.status_code == 202

    run = _wait_for_run_completion(connector["id"])
    assert run["records_seen"] == 1
    assert run["golden_count"] == 1
    assert run["failed_count"] == 0

    # Confirm the schema mapping actually happened before it reached "registry-intelligence".
    assert len(received_calls) == 1
    assert received_calls[0]["attributes"] == {"name": "Anita Devi", "date_of_birth": "1990-01-01"}
    assert "unused_field" not in received_calls[0]["attributes"]


def test_trigger_run_tracks_doubt_records_separately():
    connector = _create_flat_file_connector()
    client.post(
        f"/connectors/{connector['id']}/trigger-run",
        json={"records": [{"ration_holder_name": "Ambiguous Person", "dob": "1980-01-01"}]},
    )
    run = _wait_for_run_completion(connector["id"])
    assert run["doubt_count"] == 1
    assert run["golden_count"] == 0


def test_api_connector_fetches_live_and_ignores_body_records():
    fetch_app = FastAPI()

    @fetch_app.get("/records")
    def get_records():
        return [{"name": "Live Fetched Person", "dob": "1975-05-05"}]

    config = uvicorn.Config(fetch_app, host="127.0.0.1", port=8504, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        for _ in range(50):
            if server.started:
                break
            time.sleep(0.1)

        connector = client.post(
            "/connectors",
            json={
                "name": "External API",
                "source_type": "api",
                "department": "X",
                "connection_config": {"url": "http://127.0.0.1:8504/records"},
                "schema_mapping": {"name": "name", "dob": "date_of_birth"},
                "refresh_mode": "one_time_bulk",
                "consent_purpose_code": "x",
            },
        ).json()

        resp = client.post(f"/connectors/{connector['id']}/trigger-run")
        assert resp.status_code == 202

        run = _wait_for_run_completion(connector["id"])
        assert run["records_seen"] == 1
        assert run["golden_count"] == 1
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def test_scheduled_batch_requires_cron():
    resp = client.post(
        "/connectors",
        json={
            "name": "X",
            "source_type": "api",
            "department": "X",
            "connection_config": {},
            "schema_mapping": {},
            "refresh_mode": "scheduled_batch",
            "consent_purpose_code": "x",
        },
    )
    assert resp.status_code == 422
