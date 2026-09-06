#!/usr/bin/env python3
"""Seeds a full, narratable POC story through the platform's real APIs — no
service internals touched, just the same endpoints the frontend and any real
client would use. Run against a locally-running platform (`docker compose up`
at the repo root) or a live deployment (set API_BASE_URL) alike.

The story this tells:
  1. Three fake source databases (Ration/PDS, Land Records, Income & Asset
     Registry) get registered as connectors, each with its own field names —
     demonstrating config-driven onboarding.
  2. ~18 synthetic Delhi residents get ingested across those sources, with
     deliberate overlaps:
       - several appear in 2 sources as the SAME person with typos/reformatted
         data (no shared ID) — proving the ML matching merges them and
         enriches the golden record with fields from both sources
       - a couple share a conflicting hard identifier across two DIFFERENT
         people (a data-entry-error scenario) — landing in the Doubt Registry
       - the rest are single-source, straightforward golden records
  3. One realistic scheme — "Delhi Senior Citizen Pension" — gets registered
     with eligibility/exclusion rules, and every senior in the golden registry
     gets checked against it, using their ACTUAL ingested attributes (age
     computed from date_of_birth, income/asset data from the income-asset
     source) — not invented numbers.
  4. One Doubt Registry entry gets resolved as a human reviewer would.
  5. One remaining Doubt Registry entry is used to show the
     verification-routing path: an eligibility check against it opens a
     Verification Case, which this script then routes to `digit-adapter`
     (backed by `digit-mock` unless you've deployed real DIGIT) — since
     delivery-intelligence doesn't call digit-adapter automatically yet, this
     script does it explicitly to demonstrate the intended flow.

Usage:
    pip install -r requirements.txt
    API_BASE_URL=http://localhost:8000 python seed_demo.py
"""

import os
import random
import sys
import time
from datetime import date, datetime, timedelta

import httpx

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
GATEWAY_API_KEY = os.getenv("GATEWAY_API_KEY", "")

client = httpx.Client(
    base_url=API_BASE_URL,
    timeout=15.0,
    headers={"X-API-Key": GATEWAY_API_KEY} if GATEWAY_API_KEY else {},
)

# One entry per individual this script generates (18 today) — kept deliberately
# larger for margin. Every individual gets a UNIQUE first name (see
# NameAllocator below): with a small pool and repeats, `typo_name()`'s
# "first name -> initial" noise (e.g. "Anita" -> "A.") becomes genuinely
# ambiguous against every OTHER person sharing that first initial — the
# matching system was correctly flagging that ambiguity, but it made for a
# confusing demo where almost everything landed in the Doubt Registry instead
# of the intended clean "most things merge, a few interesting exceptions"
# story. Fix the data, not the matcher — the ambiguity was real, just
# unrepresentative of how varied real names are.
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
    """Same re-entry noise as registry-intelligence's own training data
    generator (services/registry-intelligence/app/matching/train.py) —
    keeps the ML matching honest rather than hand-picking easy duplicates."""
    parts = name.split()
    if rng.random() < 0.5 and len(parts) > 1:
        return f"{parts[0][0]}. {parts[1]}"
    word = rng.choice(parts)
    idx = rng.randrange(len(word))
    noisy = word[:idx] + word[idx + 1:] if len(word) > 1 else word
    return name.replace(word, noisy, 1)


def log(msg):
    print(f"\n>>> {msg}")


def post(path, json=None, params=None):
    resp = client.post(path, json=json, params=params)
    resp.raise_for_status()
    return resp.json()


def get(path, params=None):
    resp = client.get(path, params=params)
    resp.raise_for_status()
    return resp.json()


def wait_for_run(connector_id, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        runs = get(f"/api/connectors/connectors/{connector_id}/runs")
        if runs and runs[0]["status"] in ("completed", "failed"):
            return runs[0]
        time.sleep(0.5)
    raise TimeoutError(f"Run for connector {connector_id} did not finish in time")


def age_from_dob(dob_str):
    dob = date.fromisoformat(dob_str)
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def main():
    rng = random.Random(7)  # fixed seed — same story every run, easy to rehearse a demo

    log(f"Seeding against {API_BASE_URL}")

    # --- 1. Consent purposes ---
    log("Registering consent purposes for each source")
    for code, name, desc, cats in [
        ("ration-to-registry-match", "Ration DB to Registry Matching", "Use ration card data to resolve identity in the citizen registry.", ["name", "address", "ration_id"]),
        ("land-records-to-registry-match", "Land Records to Registry Matching", "Use land ownership records to resolve identity in the citizen registry.", ["name", "address", "aadhaar"]),
        ("income-asset-to-registry-match", "Income & Asset Registry to Registry Matching", "Use income/asset data for eligibility determination.", ["name", "annual_income", "owns_four_wheeler"]),
    ]:
        try:
            post("/api/consent/purposes", {"code": code, "name": name, "description": desc, "data_categories": cats})
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 409:
                raise

    # --- 2. Connectors ---
    log("Registering three source connectors")
    connectors = {}
    connectors["ration"] = post(
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
    connectors["land"] = post(
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
    connectors["income"] = post(
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
        print(f"    {key}: {c['id']} ({c['name']})")

    # --- 3. Synthetic citizens, distributed across sources with deliberate overlap ---
    log("Generating synthetic citizens (fixed seed — same story every run)")

    ration_records, land_records, income_records = [], [], []
    story = []  # (label, expected-outcome) for the closing summary
    names = NameAllocator(rng)  # 18 individuals below, each gets a distinct first name

    # 8 seniors who show up in BOTH ration + income sources as fuzzy duplicates —
    # the ML-matching "wow" moment: no shared ID, still merges, and the merge
    # ENRICHES the golden record with income/asset data from the second source.
    seniors_merged = []
    for i in range(8):
        name, dob, addr = rand_name(rng, names), rand_senior_dob(rng), rand_address(rng)
        income = rng.choice([120000, 180000, 300000, 450000])
        owns_car = rng.choice([0, 0, 0, 1])  # mostly no car
        ration_records.append({"ration_holder_name": name, "dob": dob, "addr": addr, "ration_card_no": f"RC{1000+i}"})
        income_records.append({"full_name": typo_name(name, rng), "dob": dob, "annual_income_inr": str(income), "vehicle_owned": str(owns_car)})
        seniors_merged.append((name, income, owns_car))
        story.append((name, f"merged (ration+income), income={income}, car={owns_car}"))

    # 4 seniors, single-source only (ration), complete enough to go golden directly —
    # will show up as "missing income/asset data" when checked for eligibility.
    for i in range(4):
        name, dob, addr = rand_name(rng, names), rand_senior_dob(rng), rand_address(rng)
        ration_records.append({"ration_holder_name": name, "dob": dob, "addr": addr, "ration_card_no": f"RC{2000+i}"})
        story.append((name, "single-source senior, no income data on file"))

    # 2 seniors deliberately excluded by the scheme (high income or car).
    for i in range(2):
        name, dob, addr = rand_name(rng, names), rand_senior_dob(rng), rand_address(rng)
        ration_records.append({"ration_holder_name": name, "dob": dob, "addr": addr, "ration_card_no": f"RC{3000+i}"})
        income_records.append({"full_name": name, "dob": dob, "annual_income_inr": "600000", "vehicle_owned": "1"})
        story.append((name, "excluded by scheme (income + car)"))

    # 2 working-age adults, land records only — unrelated to the pension scheme,
    # just proving the registry isn't senior-only.
    for i in range(2):
        name, dob, addr = rand_name(rng, names), rand_working_age_dob(rng), rand_address(rng)
        land_records.append({"owner_name": name, "date_of_birth": dob, "property_address": addr, "aadhaar_number": f"999900000{i}"})
        story.append((name, "working-age, land records only"))

    # 2 records sharing a CONFLICTING Aadhaar across different people — a data
    # entry error scenario. The first record ingests as a normal golden record
    # (nothing to conflict with yet); the second is the one that lands in the
    # Doubt Registry once the clash is detected — resolved by a human below.
    shared_aadhaar = "888800001234"
    name_a, name_b = rand_name(rng, names), rand_name(rng, names)
    land_records.append({"owner_name": name_a, "date_of_birth": rand_senior_dob(rng), "property_address": rand_address(rng), "aadhaar_number": shared_aadhaar})
    land_records.append({"owner_name": name_b, "date_of_birth": rand_senior_dob(rng), "property_address": rand_address(rng), "aadhaar_number": shared_aadhaar})
    story.append((f"{name_a} / {name_b}", "conflicting Aadhaar — Doubt Registry (resolved by human review)"))

    # A second, separate conflict — same idea, different field (ration_id) —
    # left OPEN deliberately, so there's still a Doubt Registry entry left to
    # route to DIGIT for field verification in the step after human review.
    shared_ration_id = "RC-DUPLICATE-01"
    name_c, name_d = rand_name(rng, names), rand_name(rng, names)
    ration_records.append({"ration_holder_name": name_c, "dob": rand_senior_dob(rng), "addr": rand_address(rng), "ration_card_no": shared_ration_id})
    ration_records.append({"ration_holder_name": name_d, "dob": rand_senior_dob(rng), "addr": rand_address(rng), "ration_card_no": shared_ration_id})
    story.append((f"{name_c} / {name_d}", "conflicting ration ID — Doubt Registry (routed to DIGIT for field verification)"))

    rng.shuffle(ration_records)
    rng.shuffle(land_records)
    rng.shuffle(income_records)

    # --- 4. Run ingestion for each connector ---
    log("Running ingestion for each connector")
    for key, records in [("ration", ration_records), ("land", land_records), ("income", income_records)]:
        post(f"/api/connectors/connectors/{connectors[key]['id']}/trigger-run", {"records": records})
        result = wait_for_run(connectors[key]["id"])
        print(f"    {key}: {result['records_seen']} records -> {result['golden_count']} golden, {result['doubt_count']} doubt, {result['failed_count']} failed")

    # --- 5. Register the sample scheme ---
    log("Registering scheme: Delhi Senior Citizen Pension")
    try:
        post(
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

    # --- 6. Check eligibility for every golden record using its ACTUAL attributes ---
    log("Checking eligibility for every golden record against the scheme")
    golden_records = get("/api/registry/golden-records")
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
        result = post(
            "/api/delivery/eligibility/check",
            {"citizen_golden_record_id": record["id"], "scheme_code": "delhi-senior-pension", "attributes": elig_attrs},
        )
        verdict = "ELIGIBLE" if result["eligible"] else f"not eligible ({result['failed_conditions'] + result['excluded_by']})"
        print(f"    {attrs.get('name')} (age {age}, sources={record['contributing_sources']}): {verdict}")

    # --- 7. Resolve one Doubt Registry entry as a human reviewer ---
    log("Resolving one Doubt Registry entry (human-in-the-loop)")
    doubts = get("/api/registry/doubt-records", params={"status": "open"})
    if doubts:
        doubt = doubts[0]
        print(f"    Reviewing: {doubt['attributes'].get('name')} — {len(doubt['candidate_matches'])} candidate match(es)")
        post(
            f"/api/registry/doubt-records/{doubt['id']}/resolve",
            {"resolved_by": "demo-reviewer@delhi.gov.in", "action": "promote_to_new_golden"},
        )
        print("    -> promoted to a new golden record")

    # --- 8. Route a remaining doubt record for field verification ---
    log("Routing a remaining Doubt Registry entry for field verification")
    doubts = get("/api/registry/doubt-records", params={"status": "open"})
    if doubts:
        doubt = doubts[0]
        elig = post(
            "/api/delivery/eligibility/check",
            {"citizen_doubt_record_id": doubt["id"], "scheme_code": "delhi-senior-pension", "attributes": {}},
        )
        case_id = elig["verification_case_id"]
        print(f"    Verification case opened: {case_id}")
        # delivery-intelligence doesn't call digit-adapter automatically yet —
        # doing it explicitly here demonstrates the intended flow.
        routed = post(
            f"/api/digit/verification-cases/{case_id}/route",
            {"verification_case_id": case_id, "doubt_record_id": doubt["id"], "reason": "Identity unresolved — needs field verification"},
        )
        print(f"    Routed to DIGIT (digit-mock): status={routed['status']}, process={routed.get('digit_process_instance_id')}")
        status = get(f"/api/digit/verification-cases/{case_id}/status")
        print(f"    Current DIGIT state: {status.get('digit_state')} (check again in ~25s to see it reach VERIFIED)")
    else:
        print("    No open Doubt Registry entries left to route.")

    # --- Summary ---
    log("Demo story summary")
    for name, outcome in story:
        print(f"    {name}: {outcome}")
    print(f"\nOpen the console at {API_BASE_URL.replace(':8000', ':5173') if ':8000' in API_BASE_URL else API_BASE_URL} "
          "(or your deployed frontend port) to walk through the same data visually.")


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPStatusError as e:
        print(f"\nHTTP error: {e.response.status_code} {e.response.text}", file=sys.stderr)
        sys.exit(1)
    except httpx.HTTPError as e:
        print(f"\nCould not reach {API_BASE_URL} — is the platform running? ({e})", file=sys.stderr)
        sys.exit(1)
