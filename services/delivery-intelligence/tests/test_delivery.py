import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ["DELIVERY_DB_URL"] = "sqlite:///./data/test_delivery.db"

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    yield
    db_path = "./data/test_delivery.db"
    if os.path.exists(db_path):
        os.remove(db_path)


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def _register_pension_scheme():
    return client.post(
        "/schemes",
        json={
            "scheme_code": "pension-65",
            "name": "Senior Citizen Pension",
            "eligibility_conditions": [{"field": "age", "op": "gte", "value": 65}],
            "exclusion_conditions": [
                {"field": "annual_income", "op": "gt", "value": 250000},
                {"field": "owns_four_wheeler", "op": "eq", "value": 1},
            ],
        },
    )


def test_eligibility_matrix():
    assert _register_pension_scheme().status_code == 201

    eligible = client.post(
        "/eligibility/check",
        json={"citizen_golden_record_id": "g1", "scheme_code": "pension-65", "attributes": {"age": 70, "annual_income": 100000, "owns_four_wheeler": 0}},
    ).json()
    assert eligible["eligible"] is True

    excluded = client.post(
        "/eligibility/check",
        json={"citizen_golden_record_id": "g2", "scheme_code": "pension-65", "attributes": {"age": 70, "annual_income": 100000, "owns_four_wheeler": 1}},
    ).json()
    assert excluded["eligible"] is False
    assert "owns_four_wheeler" in excluded["excluded_by"][0]

    under_age = client.post(
        "/eligibility/check",
        json={"citizen_golden_record_id": "g3", "scheme_code": "pension-65", "attributes": {"age": 40, "annual_income": 50000, "owns_four_wheeler": 0}},
    ).json()
    assert under_age["eligible"] is False
    assert "age" in under_age["failed_conditions"][0]


def test_doubt_record_opens_verification_case_and_persists():
    _register_pension_scheme()
    result = client.post(
        "/eligibility/check",
        json={"citizen_doubt_record_id": "d1", "scheme_code": "pension-65", "attributes": {}},
    ).json()
    assert result["eligible"] is False
    assert result["verification_case_id"]

    cases = client.get("/verification-cases").json()
    assert len(cases) == 1
    assert cases[0]["status"] == "open"


def test_duplicate_scheme_code_rejected():
    _register_pension_scheme()
    dup = _register_pension_scheme()
    assert dup.status_code == 409
