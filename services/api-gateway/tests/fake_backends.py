"""A single stand-in server for every downstream service api-gateway's
/api/audit/timeline fans out to, run as a real subprocess by
test_audit_timeline.py. Each real service gets its own path prefix here
(distinct SERVICE_ROUTES point at distinct prefixes on this one server) so
routes never collide even where two real services share an endpoint name
(e.g. both registry-intelligence and sunbird-adapter expose /golden-records).
Response shapes match each real service's actual schema fields exactly —
see their respective app/schemas.py / app/main.py.

Timestamps are deliberately a MIX of naive ("2026-01-01T00:00:00", no
offset) and timezone-aware ("...Z" / "+00:00") strings, matching what the
real services actually return: every service generates UTC via
datetime.now(timezone.utc), but the four backed by SQLAlchemy/SQLite
(consent, connectors, registry, delivery) lose that tzinfo on the SQLite
round-trip, while the in-memory adapters (digit, sunbird) keep it. A fake
backend that used one consistent style everywhere would never have caught
the real "can't compare offset-naive and offset-aware datetimes" bug this
was written to catch.
"""

from fastapi import FastAPI

app = FastAPI()


@app.get("/consent/health")
def consent_health():
    return {"status": "ok", "service": "consent-management"}


@app.get("/consent/consents")
def consents():
    return [
        {
            "id": "c1", "data_principal_id": "citizen-1", "purpose_id": "p1",
            "status": "granted", "collection_channel": "csc_center", "granted_by": "self",
            "consent_artifact_version": "v1", "granted_at": "2026-01-01T00:00:00",
            "expires_at": None, "revoked_at": None, "revocation_reason": None,
        },
        {
            "id": "c2", "data_principal_id": "citizen-2", "purpose_id": "p1",
            "status": "revoked", "collection_channel": "web", "granted_by": "self",
            "consent_artifact_version": "v1", "granted_at": "2026-01-02T00:00:00",
            "expires_at": None, "revoked_at": "2026-01-03T00:00:00", "revocation_reason": "opted out",
        },
    ]


@app.get("/connectors/health")
def connectors_health():
    return {"status": "ok", "service": "connector-config"}


@app.get("/connectors/connectors")
def connectors():
    return [{
        "id": "conn1", "name": "Test Connector", "source_type": "flat_file", "department": "X",
        "connection_config": {}, "schema_mapping": {}, "refresh_mode": "one_time_bulk",
        "refresh_cron": None, "consent_purpose_code": "p1", "status": "active",
        "created_at": "2026-01-01T00:00:00",
    }]


@app.get("/connectors/connectors/{connector_id}/runs")
def runs(connector_id: str):
    return [{
        "id": "run1", "connector_id": connector_id, "triggered_by": "tester", "status": "completed",
        "records_seen": 5, "golden_count": 3, "doubt_count": 1, "failed_count": 1, "error": None,
        "started_at": "2026-01-04T00:00:00", "completed_at": "2026-01-04T00:01:00",
    }]


@app.get("/registry/health")
def registry_health():
    return {"status": "ok", "service": "registry-intelligence"}


@app.get("/registry/golden-records")
def golden_records():
    return [{
        "id": "g1", "attributes": {"name": "Alice"}, "contributing_sources": ["conn1"],
        "classification": "L1_unique_complete",
        "created_at": "2026-01-05T00:00:00", "updated_at": "2026-01-05T00:00:00",
    }]


@app.get("/registry/doubt-records")
def doubt_records():
    return [{
        "id": "d1", "attributes": {"name": "Bob"}, "contributing_sources": ["conn1"],
        "classification": "L3_complete_not_unique", "candidate_matches": [], "status": "resolved",
        "created_at": "2026-01-06T00:00:00", "resolved_at": "2026-01-07T00:00:00",
        "resolved_by": "reviewer", "resolution": "promote_to_new_golden",
    }]


@app.get("/delivery/health")
def delivery_health():
    return {"status": "ok", "service": "delivery-intelligence"}


@app.get("/delivery/verification-cases")
def verification_cases():
    return [{
        "id": "vc1", "reason": "no shared identifier", "citizen_doubt_record_id": "d1",
        "scheme_code": "scheme-1", "status": "open", "created_at": "2026-01-08T00:00:00",
    }]


@app.get("/digit/health")
def digit_health():
    return {"status": "ok", "service": "digit-adapter"}


@app.get("/digit/verification-cases")
def digit_routings():
    return [{
        "verification_case_id": "vc1", "digit_process_instance_id": "proc1", "status": "routed",
        "digit_state": "PENDING_ASSIGNMENT", "error": None, "routed_at": "2026-01-09T00:00:00Z",
    }]


@app.get("/sunbird/health")
def sunbird_health():
    return {"status": "ok", "service": "sunbird-adapter"}


@app.get("/sunbird/golden-records")
def sunbird_registrations():
    return [{
        "golden_record_id": "g1", "sunbird_rc_entity_id": "ent1", "status": "registered",
        "error": None, "pushed_at": "2026-01-10T00:00:00Z",
    }]


@app.get("/openg2p/health")
def openg2p_health():
    return {"status": "ok", "service": "openg2p-sync"}


@app.get("/openg2p/sync/runs")
def sync_runs():
    return [{
        "id": "run1", "trigger_type": "manual", "triggered_by": "operator", "status": "succeeded",
        "beneficiaries_submitted": 2, "beneficiaries_synced": 2, "error": None,
        "started_at": "2026-01-11T00:00:00Z", "completed_at": "2026-01-11T00:01:00Z",
    }]
