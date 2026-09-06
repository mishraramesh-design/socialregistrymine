import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ["REGISTRY_DB_URL"] = "sqlite:///./data/test_registry.db"
os.environ["MATCH_CONFIDENCE_THRESHOLD"] = "0.85"

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    # Recreate tables via the same engine/connection pool rather than deleting
    # the SQLite file out from under it — deleting a live file while pooled
    # connections stay open can leave a connection pointing at a stale file
    # handle, corrupting state across tests in hard-to-reproduce ways.
    yield
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_deterministic_match_merges_into_same_golden_record():
    a = client.post(
        "/records/ingest",
        json={
            "source_connector_id": "ration-db",
            "source_record_id": "a",
            "attributes": {"name": "Anita Devi", "date_of_birth": "1990-01-15", "address": "12 MG Road, Delhi", "aadhaar": "1111"},
        },
    ).json()
    b = client.post(
        "/records/ingest",
        json={
            "source_connector_id": "crvs-db",
            "source_record_id": "b",
            "attributes": {"name": "Anita D.", "date_of_birth": "1990-01-15", "address": "Delhi", "aadhaar": "1111"},
        },
    ).json()
    assert a["golden_record_id"] == b["golden_record_id"]
    assert b["candidate_matches"][0]["evidence"].startswith("exact match")


def test_ml_fuzzy_match_without_any_shared_hard_id():
    """The actual point of the ML model: two records with NO id field in common at
    all should still be recognized as the same person from name/DOB/address alone."""
    a = client.post(
        "/records/ingest",
        json={
            "source_connector_id": "land-records-db",
            "source_record_id": "a",
            "attributes": {"name": "Ramesh Kumar Yadav", "date_of_birth": "1985-06-20", "address": "45 Sector 12, Rohini, Delhi, 110085"},
        },
    ).json()
    assert a["classification"] == "L1_unique_complete"

    b = client.post(
        "/records/ingest",
        json={
            "source_connector_id": "labour-db",
            "source_record_id": "b",
            "attributes": {"name": "Ramesh K. Yadav", "date_of_birth": "1985-06-20", "address": "Sector 12, Rohini, Delhi, 110085, 45"},
        },
    ).json()
    assert b["golden_record_id"] == a["golden_record_id"], f"expected ML match, got {b}"
    assert "ml_match" in b["candidate_matches"][0]["evidence"]


def test_unrelated_person_does_not_match():
    a = client.post(
        "/records/ingest",
        json={
            "source_connector_id": "land-records-db",
            "source_record_id": "a",
            "attributes": {"name": "Sunita Sharma", "date_of_birth": "1978-03-02", "address": "7 Civil Lines, Delhi, 110054"},
        },
    ).json()
    b = client.post(
        "/records/ingest",
        json={
            "source_connector_id": "labour-db",
            "source_record_id": "b",
            "attributes": {"name": "Vikram Singh Rathore", "date_of_birth": "1992-11-30", "address": "88 Model Town, Delhi, 110009"},
        },
    ).json()
    assert b["golden_record_id"] != a["golden_record_id"]
    assert b["candidate_matches"] == []


def test_conflicting_hard_ids_create_doubt_record_and_human_resolves_it():
    a = client.post(
        "/records/ingest",
        json={"source_connector_id": "ration-db", "source_record_id": "a", "attributes": {"name": "Person A", "date_of_birth": "1990-01-01", "address": "Delhi", "aadhaar": "1111"}},
    ).json()
    client.post(
        "/records/ingest",
        json={"source_connector_id": "crvs-db", "source_record_id": "b", "attributes": {"name": "Person B", "date_of_birth": "1985-01-01", "address": "Delhi", "ration_id": "9999"}},
    )
    conflict = client.post(
        "/records/ingest",
        json={"source_connector_id": "land-db", "source_record_id": "c", "attributes": {"name": "Person C", "date_of_birth": "1970-01-01", "address": "Delhi", "aadhaar": "1111", "ration_id": "9999"}},
    ).json()
    assert conflict["classification"] == "L3_complete_not_unique"
    doubt_id = conflict["doubt_record_id"]
    assert doubt_id

    resolved = client.post(
        f"/doubt-records/{doubt_id}/resolve",
        json={"resolved_by": "reviewer1", "action": "merge_into_golden", "target_golden_record_id": a["golden_record_id"]},
    ).json()
    assert resolved["status"] == "resolved"

    # State survives across requests — this is the point of persistent storage.
    fetched = client.get(f"/doubt-records/{doubt_id}").json()
    assert fetched["status"] == "resolved"
    assert fetched["resolved_by"] == "reviewer1"


def test_data_persists_across_a_fresh_db_session():
    """Regression guard for the in-memory -> SQLite migration: a second TestClient
    request must see what a prior request wrote, without relying on process state."""
    created = client.post(
        "/records/ingest",
        json={"source_connector_id": "x", "source_record_id": "1", "attributes": {"name": "Persist Test", "date_of_birth": "2000-01-01", "address": "Somewhere"}},
    ).json()
    fetched = client.get(f"/golden-records/{created['golden_record_id']}").json()
    assert fetched["attributes"]["name"] == "Persist Test"
