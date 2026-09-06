"""demo-seeder: runs the platform's synthetic POC story (the same story as
`scripts/seed_demo.py`) from inside the deployment itself, so a demo can be
seeded with one click from the frontend instead of requiring shell access.

Talks to every other service exclusively through `api-gateway`'s public
`/api/<service>/*` routes — the same contract the frontend and the standalone
CLI script use — so this is not a shortcut around the platform's own APIs,
just the same client logic running server-side. State is in-memory and
single-run-at-a-time by design: this is a POC demo utility, not a job queue.
"""

import os
import random
import threading
import time
from datetime import date, datetime, timedelta
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Demo Seeder", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

API_BASE_URL = os.getenv("API_BASE_URL", "http://api-gateway:8000")
GATEWAY_API_KEY = os.getenv("GATEWAY_API_KEY", "")

FIRST_NAMES = [
    "Ramesh", "Sunita", "Anita", "Vikram", "Pooja", "Rajesh", "Kavita", "Suresh",
    "Meena", "Ashok", "Geeta", "Mahesh", "Lata", "Prakash", "Usha", "Vinod",
    "Radha", "Deepak", "Sarita", "Manoj", "Kiran", "Naresh", "Shanti", "Om",
    "Kamla", "Harish", "Nirmala", "Yogesh",
]
LAST_NAMES = [
    "Kumar", "Sharma", "Yadav", "Singh", "Verma", "Gupta", "Devi", "Rathore",
    "Chauhan", "Mishra", "Tiwari", "Saxena",
]
LOCALITIES = [
    ("Sector 12, Rohini", "110085"), ("Vasant Kunj", "110070"), ("Karol Bagh", "110005"),
    ("Lajpat Nagar", "110024"), ("Janakpuri", "110058"), ("Mayur Vihar Phase 1", "110091"),
    ("Civil Lines", "110054"), ("Pitampura", "110034"), ("Saket", "110017"),
]


class NameAllocator:
    """Hands out first names one at a time, shuffled but never repeated —
    every individual in the generated dataset gets a distinct first name."""

    def __init__(self, rng, pool=FIRST_NAMES):
        self._pool = list(pool)
        rng.shuffle(self._pool)

    def next_first_name(self):
        if not self._pool:
            raise ValueError("Ran out of unique first names — add more to FIRST_NAMES")
        return self._pool.pop()


def rand_name(rng, names: NameAllocator):
    return f"{names.next_first_name()} {rng.choice(LAST_NAMES)}"


def rand_address(rng):
    locality, pin = rng.choice(LOCALITIES)
    return f"{rng.randint(1, 99)} {locality}, Delhi, {pin}"


def rand_senior_dob(rng):
    age = rng.randint(66, 82)
    return (date.today() - timedelta(days=age * 365 + rng.randint(0, 300))).isoformat()


def rand_working_age_dob(rng):
    age = rng.randint(30, 55)
    return (date.today() - timedelta(days=age * 365 + rng.randint(0, 300))).isoformat()


def typo_name(name, rng):
    parts = name.split()
    if rng.random() < 0.5 and len(parts) > 1:
        return f"{parts[0][0]}. {parts[1]}"
    word = rng.choice(parts)
    idx = rng.randrange(len(word))
    noisy = word[:idx] + word[idx + 1:] if len(word) > 1 else word
    return name.replace(word, noisy, 1)


def age_from_dob(dob_str):
    dob = date.fromisoformat(dob_str)
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


class SeedState:
    """Single-run-at-a-time in-memory state, guarded by a lock. A new /seed
    call while one is running is rejected rather than queued — this is a demo
    trigger, not a job scheduler."""

    def __init__(self):
        self._lock = threading.Lock()
        self.reset()

    def reset(self):
        self.status = "idle"  # idle | running | completed | failed
        self.started_at: Optional[str] = None
        self.finished_at: Optional[str] = None
        self.log: list[str] = []
        self.story: list[dict] = []
        self.error: Optional[str] = None

    def start(self) -> bool:
        with self._lock:
            if self.status == "running":
                return False
            self.reset()
            self.status = "running"
            self.started_at = datetime.utcnow().isoformat() + "Z"
            return True

    def append(self, msg: str):
        self.log.append(msg)

    def finish(self, ok: bool, error: Optional[str] = None):
        self.status = "completed" if ok else "failed"
        self.finished_at = datetime.utcnow().isoformat() + "Z"
        self.error = error

    def snapshot(self) -> dict:
        return {
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "log": list(self.log),
            "story": list(self.story),
            "error": self.error,
        }


state = SeedState()


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=API_BASE_URL,
        timeout=15.0,
        headers={"X-API-Key": GATEWAY_API_KEY} if GATEWAY_API_KEY else {},
    )


def _post(client, path, json=None):
    resp = client.post(path, json=json)
    resp.raise_for_status()
    return resp.json()


def _get(client, path, params=None):
    resp = client.get(path, params=params)
    resp.raise_for_status()
    return resp.json()


def _wait_for_run(client, connector_id, timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        runs = _get(client, f"/api/connectors/connectors/{connector_id}/runs")
        if runs and runs[0]["status"] in ("completed", "failed"):
            return runs[0]
        time.sleep(0.5)
    raise TimeoutError(f"Run for connector {connector_id} did not finish in time")


def _run_story(client, log):
    rng = random.Random(7)  # fixed seed — same story every run

    log(f"Seeding against {API_BASE_URL}")

    log("Registering consent purposes for each source")
    for code, name, desc, cats in [
        ("ration-to-registry-match", "Ration DB to Registry Matching", "Use ration card data to resolve identity in the citizen registry.", ["name", "address", "ration_id"]),
        ("land-records-to-registry-match", "Land Records to Registry Matching", "Use land ownership records to resolve identity in the citizen registry.", ["name", "address", "aadhaar"]),
        ("income-asset-to-registry-match", "Income & Asset Registry to Registry Matching", "Use income/asset data for eligibility determination.", ["name", "annual_income", "owns_four_wheeler"]),
    ]:
        try:
            _post(client, "/api/consent/purposes", {"code": code, "name": name, "description": desc, "data_categories": cats})
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 409:
                raise

    log("Registering three source connectors")
    connectors = {}
    connectors["ration"] = _post(
        client,
        "/api/connectors/connectors",
        {
            "name": "Delhi Food & Civil Supply — Ration DB",
            "source_type": "flat_file",
            "department": "Food & Civil Supply",
            "connection_config": {},
            "schema_mapping": {"ration_holder_name": "name", "dob": "date_of_birth", "addr": "address", "ration_card_no": "ration_id"},
            "refresh_mode": "one_time_bulk",
            "consent_purpose_code": "ration-to-registry-match",
        },
    )
    connectors["land"] = _post(
        client,
        "/api/connectors/connectors",
        {
            "name": "Delhi Land Records DB",
            "source_type": "flat_file",
            "department": "Revenue",
            "connection_config": {},
            "schema_mapping": {"owner_name": "name", "date_of_birth": "date_of_birth", "property_address": "address", "aadhaar_number": "aadhaar"},
            "refresh_mode": "one_time_bulk",
            "consent_purpose_code": "land-records-to-registry-match",
        },
    )
    connectors["income"] = _post(
        client,
        "/api/connectors/connectors",
        {
            "name": "Delhi Income & Asset Registry",
            "source_type": "flat_file",
            "department": "Finance",
            "connection_config": {},
            "schema_mapping": {"full_name": "name", "dob": "date_of_birth", "annual_income_inr": "annual_income", "vehicle_owned": "owns_four_wheeler"},
            "refresh_mode": "one_time_bulk",
            "consent_purpose_code": "income-asset-to-registry-match",
        },
    )
    for key, c in connectors.items():
        log(f"    {key}: {c['id']} ({c['name']})")

    log("Generating synthetic citizens (fixed seed — same story every run)")
    ration_records, land_records, income_records = [], [], []
    story = []
    names = NameAllocator(rng)

    seniors_merged = []
    for i in range(8):
        name, dob, addr = rand_name(rng, names), rand_senior_dob(rng), rand_address(rng)
        income = rng.choice([120000, 180000, 300000, 450000])
        owns_car = rng.choice([0, 0, 0, 1])
        ration_records.append({"ration_holder_name": name, "dob": dob, "addr": addr, "ration_card_no": f"RC{1000+i}"})
        income_records.append({"full_name": typo_name(name, rng), "dob": dob, "annual_income_inr": str(income), "vehicle_owned": str(owns_car)})
        seniors_merged.append((name, income, owns_car))
        story.append((name, f"merged (ration+income), income={income}, car={owns_car}"))

    for i in range(4):
        name, dob, addr = rand_name(rng, names), rand_senior_dob(rng), rand_address(rng)
        ration_records.append({"ration_holder_name": name, "dob": dob, "addr": addr, "ration_card_no": f"RC{2000+i}"})
        story.append((name, "single-source senior, no income data on file"))

    for i in range(2):
        name, dob, addr = rand_name(rng, names), rand_senior_dob(rng), rand_address(rng)
        ration_records.append({"ration_holder_name": name, "dob": dob, "addr": addr, "ration_card_no": f"RC{3000+i}"})
        income_records.append({"full_name": name, "dob": dob, "annual_income_inr": "600000", "vehicle_owned": "1"})
        story.append((name, "excluded by scheme (income + car)"))

    for i in range(2):
        name, dob, addr = rand_name(rng, names), rand_working_age_dob(rng), rand_address(rng)
        land_records.append({"owner_name": name, "date_of_birth": dob, "property_address": addr, "aadhaar_number": f"999900000{i}"})
        story.append((name, "working-age, land records only"))

    shared_aadhaar = "888800001234"
    name_a, name_b = rand_name(rng, names), rand_name(rng, names)
    land_records.append({"owner_name": name_a, "date_of_birth": rand_senior_dob(rng), "property_address": rand_address(rng), "aadhaar_number": shared_aadhaar})
    land_records.append({"owner_name": name_b, "date_of_birth": rand_senior_dob(rng), "property_address": rand_address(rng), "aadhaar_number": shared_aadhaar})
    story.append((f"{name_a} / {name_b}", "conflicting Aadhaar — Doubt Registry (resolved by human review)"))

    shared_ration_id = "RC-DUPLICATE-01"
    name_c, name_d = rand_name(rng, names), rand_name(rng, names)
    ration_records.append({"ration_holder_name": name_c, "dob": rand_senior_dob(rng), "addr": rand_address(rng), "ration_card_no": shared_ration_id})
    ration_records.append({"ration_holder_name": name_d, "dob": rand_senior_dob(rng), "addr": rand_address(rng), "ration_card_no": shared_ration_id})
    story.append((f"{name_c} / {name_d}", "conflicting ration ID — Doubt Registry (routed to DIGIT for field verification)"))

    rng.shuffle(ration_records)
    rng.shuffle(land_records)
    rng.shuffle(income_records)

    log("Running ingestion for each connector")
    for key, records in [("ration", ration_records), ("land", land_records), ("income", income_records)]:
        _post(client, f"/api/connectors/connectors/{connectors[key]['id']}/trigger-run", {"records": records})
        result = _wait_for_run(client, connectors[key]["id"])
        log(f"    {key}: {result['records_seen']} records -> {result['golden_count']} golden, {result['doubt_count']} doubt, {result['failed_count']} failed")

    log("Registering scheme: Delhi Senior Citizen Pension")
    try:
        _post(
            client,
            "/api/delivery/schemes",
            {
                "scheme_code": "delhi-senior-pension",
                "name": "Delhi Senior Citizen Pension",
                "eligibility_conditions": [{"field": "age", "op": "gte", "value": 65}],
                "exclusion_conditions": [
                    {"field": "annual_income", "op": "gt", "value": 250000},
                    {"field": "owns_four_wheeler", "op": "eq", "value": 1},
                ],
            },
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code != 409:
            raise

    log("Checking eligibility for every golden record against the scheme")
    golden_records = _get(client, "/api/registry/golden-records")
    for record in golden_records:
        attrs = record["attributes"]
        dob = attrs.get("date_of_birth")
        if not dob:
            continue
        age = age_from_dob(dob)
        if age < 60:
            continue
        elig_attrs = {"age": float(age)}
        if "annual_income" in attrs:
            elig_attrs["annual_income"] = float(attrs["annual_income"])
        if "owns_four_wheeler" in attrs:
            elig_attrs["owns_four_wheeler"] = float(attrs["owns_four_wheeler"])
        result = _post(
            client,
            "/api/delivery/eligibility/check",
            {"citizen_golden_record_id": record["id"], "scheme_code": "delhi-senior-pension", "attributes": elig_attrs},
        )
        verdict = "ELIGIBLE" if result["eligible"] else f"not eligible ({result['failed_conditions'] + result['excluded_by']})"
        log(f"    {attrs.get('name')} (age {age}, sources={record['contributing_sources']}): {verdict}")

    log("Resolving one Doubt Registry entry (human-in-the-loop)")
    doubts = _get(client, "/api/registry/doubt-records", params={"status": "open"})
    if doubts:
        doubt = doubts[0]
        log(f"    Reviewing: {doubt['attributes'].get('name')} — {len(doubt['candidate_matches'])} candidate match(es)")
        _post(
            client,
            f"/api/registry/doubt-records/{doubt['id']}/resolve",
            {"resolved_by": "demo-reviewer@delhi.gov.in", "action": "promote_to_new_golden"},
        )
        log("    -> promoted to a new golden record")

    log("Routing a remaining Doubt Registry entry for field verification")
    doubts = _get(client, "/api/registry/doubt-records", params={"status": "open"})
    if doubts:
        doubt = doubts[0]
        elig = _post(
            client,
            "/api/delivery/eligibility/check",
            {"citizen_doubt_record_id": doubt["id"], "scheme_code": "delhi-senior-pension", "attributes": {}},
        )
        case_id = elig["verification_case_id"]
        log(f"    Verification case opened: {case_id}")
        routed = _post(
            client,
            f"/api/digit/verification-cases/{case_id}/route",
            {"verification_case_id": case_id, "doubt_record_id": doubt["id"], "reason": "Identity unresolved — needs field verification"},
        )
        log(f"    Routed to DIGIT: status={routed['status']}, process={routed.get('digit_process_instance_id')}")
        status = _get(client, f"/api/digit/verification-cases/{case_id}/status")
        log(f"    Current DIGIT state: {status.get('digit_state')} (check again shortly to see it progress)")
    else:
        log("    No open Doubt Registry entries left to route.")

    return [{"name": name, "outcome": outcome} for name, outcome in story]


def _run_in_background():
    try:
        with _client() as client:
            story = _run_story(client, state.append)
        state.story = story
        state.finish(ok=True)
    except httpx.HTTPStatusError as e:
        state.append(f"HTTP error: {e.response.status_code} {e.response.text}")
        state.finish(ok=False, error=f"HTTP {e.response.status_code}: {e.response.text[:300]}")
    except httpx.HTTPError as e:
        state.append(f"Could not reach {API_BASE_URL} — is the platform running? ({e})")
        state.finish(ok=False, error=str(e))
    except Exception as e:  # noqa: BLE001 — surfaced to the caller via /status, not swallowed
        state.append(f"Unexpected error: {e}")
        state.finish(ok=False, error=str(e))


class SeedResponse(BaseModel):
    status: str
    detail: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/seed", response_model=SeedResponse)
def seed():
    started = state.start()
    if not started:
        raise HTTPException(409, "A seed run is already in progress")
    thread = threading.Thread(target=_run_in_background, daemon=True)
    thread.start()
    return SeedResponse(status="started", detail="Seeding started in the background — poll GET /status")


@app.get("/status")
def status():
    return state.snapshot()
