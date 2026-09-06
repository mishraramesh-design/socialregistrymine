"""inji-adapter: issues and verifies portable credentials for a golden record's
identity/eligibility via a separately-deployed Inji Certify + Inji Verify instance.

Inji Certify implements OpenID4VCI (draft 13) — credential issuance is
**discovery-based**, not a fixed path: the issuer publishes its actual
`credential_endpoint` at `/.well-known/openid-credential-issuer`, and a client is
expected to fetch that metadata first rather than assume a URL. This adapter does
that discovery on every issuance call rather than hardcoding a path, which is the
protocol-correct approach (and avoids baking in a path that changes across Inji
Certify versions/deployments).

What's NOT pinned here: the OAuth2 client credentials this adapter authenticates
with (INJI_CLIENT_ID/INJI_CLIENT_SECRET) are issued by whoever operates the Inji
Certify instance — an operational setup step, not something this adapter can
generate. Inji Verify's verification API path is version-specific and not
confirmed against a live instance; INJI_VERIFY_PATH defaults to a reasonable
guess and should be checked against the deployed Inji Verify's own API docs
before relying on it.
"""

import os
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

INJI_CERTIFY_BASE_URL = os.getenv("INJI_CERTIFY_BASE_URL", "http://localhost:8084")
INJI_VERIFY_BASE_URL = os.getenv("INJI_VERIFY_BASE_URL", "http://localhost:8085")
INJI_VERIFY_PATH = os.getenv("INJI_VERIFY_PATH", "/v1/verify/vc-verification")  # unconfirmed — see module docstring
INJI_CLIENT_ID = os.getenv("INJI_CLIENT_ID", "")
INJI_CLIENT_SECRET = os.getenv("INJI_CLIENT_SECRET", "")
INJI_TOKEN_URL = os.getenv("INJI_TOKEN_URL", "")  # the issuer's OAuth token endpoint, from their own setup docs

app = FastAPI(
    title="Inji Adapter",
    description="Issues and verifies portable credentials via Inji Certify (OpenID4VCI) and Inji Verify.",
    version="0.1.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class IssuanceStatus(str, Enum):
    ISSUED = "issued"
    FAILED = "failed"


class IssueCredentialRequest(BaseModel):
    golden_record_id: str
    credential_type: str = "CitizenIdentityCredential"
    claims: Dict[str, str]


class IssuanceRecord(BaseModel):
    golden_record_id: str
    credential_type: str
    status: IssuanceStatus
    credential: Optional[dict] = None
    error: Optional[str] = None
    issued_at: datetime


class VerifyCredentialRequest(BaseModel):
    verifiable_credential: dict


class VerificationResult(BaseModel):
    valid: bool
    detail: Optional[str] = None


def _get_access_token(client: httpx.Client) -> Optional[str]:
    if not INJI_TOKEN_URL or not INJI_CLIENT_ID:
        return None
    resp = client.post(
        INJI_TOKEN_URL,
        data={"grant_type": "client_credentials", "client_id": INJI_CLIENT_ID, "client_secret": INJI_CLIENT_SECRET},
    )
    resp.raise_for_status()
    return resp.json().get("access_token")


@app.post("/golden-records/{golden_record_id}/issue-credential", response_model=IssuanceRecord, status_code=201)
def issue_credential(golden_record_id: str, payload: IssueCredentialRequest):
    if golden_record_id != payload.golden_record_id:
        raise HTTPException(422, "Path golden_record_id must match payload")

    now = datetime.now(timezone.utc)
    try:
        with httpx.Client(timeout=10.0) as client:
            # OpenID4VCI discovery — find the real credential_endpoint rather than assume one.
            metadata = client.get(f"{INJI_CERTIFY_BASE_URL}/.well-known/openid-credential-issuer")
            metadata.raise_for_status()
            credential_endpoint = metadata.json()["credential_endpoint"]

            access_token = _get_access_token(client)
            headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}

            resp = client.post(
                credential_endpoint,
                json={"format": "ldp_vc", "credential_definition": {"type": [payload.credential_type]}, "claims": payload.claims},
                headers=headers,
            )
            resp.raise_for_status()
            credential = resp.json()

        record = IssuanceRecord(
            golden_record_id=golden_record_id,
            credential_type=payload.credential_type,
            status=IssuanceStatus.ISSUED,
            credential=credential,
            issued_at=now,
        )
    except (httpx.HTTPError, KeyError) as exc:
        record = IssuanceRecord(
            golden_record_id=golden_record_id,
            credential_type=payload.credential_type,
            status=IssuanceStatus.FAILED,
            error=f"Inji Certify unreachable, misconfigured, or rejected the request: {exc}",
            issued_at=now,
        )

    return record


@app.post("/credentials/verify", response_model=VerificationResult)
def verify_credential(payload: VerifyCredentialRequest):
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(f"{INJI_VERIFY_BASE_URL}{INJI_VERIFY_PATH}", json=payload.verifiable_credential)
            resp.raise_for_status()
            result = resp.json()
        return VerificationResult(valid=bool(result.get("valid") or result.get("verificationStatus") == "SUCCESS"), detail=str(result))
    except httpx.HTTPError as exc:
        return VerificationResult(valid=False, detail=f"Inji Verify unreachable or rejected the request: {exc}")


@app.get("/health")
def health():
    """See sunbird-adapter's health handler for why this probes the
    downstream DPGs rather than just reporting this service's own liveness.
    Two targets here since Inji Certify and Inji Verify are separate
    services that can each be up or down independently."""
    def _reachable(url: str) -> bool:
        try:
            with httpx.Client(timeout=2.0) as client:
                client.get(url)
            return True
        except httpx.HTTPError:
            return False

    return {
        "status": "ok",
        "service": "inji-adapter",
        "downstream": {
            "certify": {"name": "Inji Certify", "reachable": _reachable(INJI_CERTIFY_BASE_URL)},
            "verify": {"name": "Inji Verify", "reachable": _reachable(INJI_VERIFY_BASE_URL)},
        },
    }
