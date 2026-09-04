import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ["CONSENT_DB_URL"] = "sqlite:///./data/test_consent.db"

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    yield
    db_path = "./data/test_consent.db"
    if os.path.exists(db_path):
        os.remove(db_path)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_purpose_and_consent_lifecycle():
    purpose_resp = client.post(
        "/purposes",
        json={
            "code": "ration-to-registry-match",
            "name": "Ration DB to Registry Matching",
            "description": "Use ration card data to resolve identity in the citizen registry.",
            "data_categories": ["name", "address", "ration_id"],
            "source_system": "PDS",
            "retention_period_days": 730,
        },
    )
    assert purpose_resp.status_code == 201

    consent_resp = client.post(
        "/consents",
        json={
            "data_principal_id": "citizen-123",
            "purpose_code": "ration-to-registry-match",
            "collection_channel": "csc_center",
            "granted_by": "self",
        },
    )
    assert consent_resp.status_code == 201
    consent = consent_resp.json()
    assert consent["status"] == "granted"

    listing = client.get("/consents", params={"data_principal_id": "citizen-123"})
    assert len(listing.json()) == 1

    revoke_resp = client.post(
        f"/consents/{consent['id']}/revoke",
        json={"reason": "citizen requested opt-out", "actor": "citizen-123"},
    )
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["status"] == "revoked"

    audit_resp = client.get(f"/consents/{consent['id']}/audit")
    actions = [entry["action"] for entry in audit_resp.json()]
    assert "created" in actions
    assert "revoked" in actions


def test_consent_requires_registered_purpose():
    resp = client.post(
        "/consents",
        json={
            "data_principal_id": "citizen-999",
            "purpose_code": "does-not-exist",
            "collection_channel": "web",
        },
    )
    assert resp.status_code == 404
