"""connector-config: no-code source onboarding.

Registering a new government database or API as a source is a config
operation here, not a new integration project — the payload below is
everything a generic ingestion engine needs to pull from it and map it
onto the canonical citizen/family schema.
"""

import os
from datetime import datetime, timezone
from typing import List

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import models
from .database import Base, engine, get_db
from .schemas import ConnectorCreate, ConnectorOut, ConnectorStatus, IngestionRunOut, RefreshMode

os.makedirs("./data", exist_ok=True)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Connector Config Service",
    description="No-code registration of source databases/APIs and their mapping "
    "to the canonical citizen/family schema.",
    version="0.2.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


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
def trigger_run(connector_id: str, triggered_by: str = "operator", db: Session = Depends(get_db)):
    """Kicks off an ingestion run for this source. Records the run's intent — the
    actual extract/standardize/match pipeline is owned by registry-intelligence,
    which this endpoint would call in the next build phase."""
    connector = db.get(models.Connector, connector_id)
    if not connector:
        raise HTTPException(404, "Connector not found")
    run = models.IngestionRun(
        connector_id=connector_id,
        triggered_by=triggered_by,
        status="queued",
        started_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
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
