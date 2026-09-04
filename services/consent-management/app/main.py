import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models
from .database import Base, engine
from .routers import consent, purpose

os.makedirs("./data", exist_ok=True)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Consent Management Service",
    description="DPDP-Act-aligned consent capture, purpose limitation, revocation, and audit trail "
    "for data shared between source systems, the Social Registry, and Benefit Delivery.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(purpose.router)
app.include_router(consent.router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok", "service": "consent-management"}
