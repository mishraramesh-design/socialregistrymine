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

from app.database import Base, engine
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
    # Recreate tables via the same engine/pool rather than deleting the SQLite
    # file out from under it — see registry-intelligence/tests for why.
    received_calls.clear()
    yield
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


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


def test_add_missing_columns_patches_a_pre_existing_table_without_losing_rows():
    """Regression test for a real production incident: a long-lived SQLite
    volume from before golden_count/doubt_count/failed_count/error were added
    to IngestionRun had none of those columns, so the first write to any of
    them 500'd. create_all() alone can't fix this — it only creates tables
    that don't exist, never alters ones that do."""
    from app.database import add_missing_columns

    with engine.connect() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS ingestion_runs")
        conn.exec_driver_sql(
            """
            CREATE TABLE ingestion_runs (
                id VARCHAR NOT NULL PRIMARY KEY,
                connector_id VARCHAR NOT NULL,
                triggered_by VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                records_seen INTEGER NOT NULL,
                started_at DATETIME,
                completed_at DATETIME
            )
            """
        )
        conn.exec_driver_sql(
            "INSERT INTO ingestion_runs VALUES ('r1', 'c1', 'test', 'completed', 5, NULL, NULL)"
        )
        conn.commit()

    add_missing_columns()

    with engine.connect() as conn:
        columns = {row[1] for row in conn.exec_driver_sql('PRAGMA table_info("ingestion_runs")')}
        assert {"golden_count", "doubt_count", "failed_count", "error"} <= columns

        row = conn.exec_driver_sql(
            "SELECT id, golden_count, doubt_count, failed_count, error FROM ingestion_runs WHERE id = 'r1'"
        ).fetchone()
        assert row == ("r1", 0, 0, 0, None)
