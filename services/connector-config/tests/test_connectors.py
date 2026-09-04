import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ["CONNECTOR_DB_URL"] = "sqlite:///./data/test_connectors.db"

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    yield
    db_path = "./data/test_connectors.db"
    if os.path.exists(db_path):
        os.remove(db_path)


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_create_list_and_trigger_run():
    created = client.post(
        "/connectors",
        json={
            "name": "Delhi Ration DB",
            "source_type": "database",
            "department": "Food & Civil Supply",
            "connection_config": {"host": "internal-db"},
            "schema_mapping": {"ration_holder_name": "name"},
            "refresh_mode": "one_time_bulk",
            "consent_purpose_code": "ration-to-registry-match",
        },
    )
    assert created.status_code == 201
    connector = created.json()
    assert connector["status"] == "draft"

    listing = client.get("/connectors").json()
    assert len(listing) == 1

    run = client.post(f"/connectors/{connector['id']}/trigger-run", params={"triggered_by": "operator1"})
    assert run.status_code == 202
    assert run.json()["status"] == "queued"

    runs = client.get(f"/connectors/{connector['id']}/runs").json()
    assert len(runs) == 1

    status_update = client.patch(f"/connectors/{connector['id']}/status", params={"status": "active"})
    assert status_update.json()["status"] == "active"

    # Persisted across requests, not process memory.
    refetched = client.get(f"/connectors/{connector['id']}").json()
    assert refetched["status"] == "active"


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
