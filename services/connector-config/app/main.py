"""connector-config: no-code source onboarding.

Registering a new government database or API as a source is a config
operation here, not a new integration project — the payload below is
everything a generic ingestion engine needs to pull from it and map it
onto the canonical citizen/family schema.

Triggering a run actually ingests records into registry-intelligence (see
`_run_ingestion` below), not just records that a run happened:
- `api` connectors fetch live: a GET to `connection_config["url"]`, expecting
  a JSON array of objects.
- `database`/`flat_file` connectors have no live driver yet (that's real
  per-DBMS integration work, not a config change) — records must be supplied
  in the trigger-run request body instead. This is the honest stand-in until
  real DB/file connectivity is built.
Either way, each raw record is mapped through the connector's `schema_mapping`
and POSTed to registry-intelligence's `/records/ingest`, and the run tracks
how many landed as golden vs. doubt vs. failed.
"""

import os
from datetime import datetime, timezone
from typing import List, Optional

import httpx
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import models
from .database import Base, SessionLocal, engine, get_db
from .schemas import (
    ConnectorCreate,
    ConnectorOut,
    ConnectorStatus,
    IngestionRunOut,
    RefreshMode,
    TriggerRunRequest,
)

REGISTRY_SERVICE_URL = os.getenv("REGISTRY_SERVICE_URL", "http://registry-intelligence:8003")

os.makedirs("./data", exist_ok=True)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Connector Config Service",
    description="No-code registration of source databases/APIs and their mapping "
    "to the canonical citizen/family schema.",
    version="0.3.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _map_record(schema_mapping: dict, raw: dict) -> dict:
    return {canonical: str(raw[source]) for source, canonical in schema_mapping.items() if source in raw and raw[source] is not None}


def _run_ingestion(run_id: str, connector_id: str, records_supplied: Optional[List[dict]]):
    """Runs in the background after trigger-run returns. Opens its own DB
    session since the request-scoped one is gone by the time this executes.
    `records_supplied` is passed in directly as a task argument (not read off
    the run/connector rows) since it's request data, not something persisted."""
    db = SessionLocal()
    try:
        run = db.get(models.IngestionRun, run_id)
        connector = db.get(models.Connector, connector_id)
        if not run or not connector:
            return

        run.status = "running"
        db.commit()

        records: List[dict] = []
        if connector.source_type == "api":
            url = connector.connection_config.get("url")
            if not url:
                run.status = "failed"
                run.error = "source_type=api but connection_config has no 'url'"
                run.completed_at = datetime.now(timezone.utc)
                db.commit()
                return
            try:
                with httpx.Client(timeout=15.0) as client:
                    resp = client.get(url)
                    resp.raise_for_status()
                    records = resp.json()
                    if not isinstance(records, list):
                        raise ValueError("expected a JSON array of records")
            except (httpx.HTTPError, ValueError) as exc:
                run.status = "failed"
                run.error = f"Could not fetch records from {url}: {exc}"
                run.completed_at = datetime.now(timezone.utc)
                db.commit()
                return
        else:
            records = records_supplied or []
            if not records:
                run.status = "failed"
                run.error = (
                    f"source_type={connector.source_type} has no live driver yet — pass 'records' in the "
                    "trigger-run request body."
                )
                run.completed_at = datetime.now(timezone.utc)
                db.commit()
                return

        golden = doubt = failed = 0
        try:
            with httpx.Client(timeout=15.0) as client:
                for i, raw in enumerate(records):
                    attributes = _map_record(connector.schema_mapping, raw)
                    try:
                        resp = client.post(
                            f"{REGISTRY_SERVICE_URL}/records/ingest",
                            json={
                                "source_connector_id": connector.id,
                                "source_record_id": str(raw.get("id", f"{connector.id}-{i}")),
                                "attributes": attributes,
                            },
                        )
                        resp.raise_for_status()
                        result = resp.json()
                        if result.get("golden_record_id"):
                            golden += 1
                        elif result.get("doubt_record_id"):
                            doubt += 1
                    except httpx.HTTPError:
                        failed += 1
        finally:
            run.records_seen = len(records)
            run.golden_count = golden
            run.doubt_count = doubt
            run.failed_count = failed
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()


@app.post("/connectors", response_model=ConnectorOut, status_code=201)
def create_connector(payload: ConnectorCreate, db: Session = Depends(get_db)):
    if payload.refresh_mode == RefreshMode.SCHEDULED_BATCH and not payload.refresh_cron:
        raise HTTPException(422, "refresh_cron is required when refresh_mode=scheduled_batch")

    connector = models.Connector(**payload.model_dump(mode="json"))
    db.add(connector)
    db.commit()
    db.refresh(connector)
    return connector


@app.get("/connectors", response_model=List[ConnectorOut])
def list_connectors(db: Session = Depends(get_db)):
    return db.query(models.Connector).order_by(models.Connector.created_at.desc()).all()


@app.get("/connectors/{connector_id}", response_model=ConnectorOut)
def get_connector(connector_id: str, db: Session = Depends(get_db)):
    connector = db.get(models.Connector, connector_id)
    if not connector:
        raise HTTPException(404, "Connector not found")
    return connector


@app.patch("/connectors/{connector_id}/status", response_model=ConnectorOut)
def set_connector_status(connector_id: str, status: ConnectorStatus, db: Session = Depends(get_db)):
    connector = db.get(models.Connector, connector_id)
    if not connector:
        raise HTTPException(404, "Connector not found")
    connector.status = status.value
    db.commit()
    db.refresh(connector)
    return connector


@app.post("/connectors/{connector_id}/trigger-run", response_model=IngestionRunOut, status_code=202)
def trigger_run(
    connector_id: str,
    background_tasks: BackgroundTasks,
    payload: TriggerRunRequest = TriggerRunRequest(),
    triggered_by: str = "operator",
    db: Session = Depends(get_db),
):
    connector = db.get(models.Connector, connector_id)
    if not connector:
        raise HTTPException(404, "Connector not found")
    if connector.source_type != "api" and not payload.records:
        raise HTTPException(
            422,
            f"source_type={connector.source_type} has no live driver — pass 'records' in the request body.",
        )

    run = models.IngestionRun(
        connector_id=connector_id,
        triggered_by=triggered_by,
        status="queued",
        started_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    background_tasks.add_task(_run_ingestion, run.id, connector_id, payload.records)
    return run


@app.get("/connectors/{connector_id}/runs", response_model=List[IngestionRunOut])
def list_runs(connector_id: str, db: Session = Depends(get_db)):
    if not db.get(models.Connector, connector_id):
        raise HTTPException(404, "Connector not found")
    return (
        db.query(models.IngestionRun)
        .filter_by(connector_id=connector_id)
        .order_by(models.IngestionRun.started_at.desc())
        .all()
    )


@app.get("/health")
def health():
    return {"status": "ok", "service": "connector-config"}
