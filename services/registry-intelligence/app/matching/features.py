"""Pairwise similarity features between two canonical-schema records.

Kept small and interpretable (4 features) rather than throwing a large feature
bank at a logistic regression — this is a base model meant to generalize across
any state's data on day one (per docs/architecture.md's matching strategy), not
one tuned to a single deployment's quirks. Every feature here is schema-agnostic:
it only assumes a record MAY have `name`, `date_of_birth`, `address` fields —
exactly what connector-config's schema mapping guarantees regardless of source.
"""

from typing import Dict, List

from rapidfuzz import fuzz

try:
    import jellyfish
except ImportError:  # pragma: no cover
    jellyfish = None

FEATURE_NAMES = ["name_similarity", "name_phonetic_match", "dob_similarity", "address_similarity"]


def name_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return fuzz.token_sort_ratio(a, b) / 100.0


def name_phonetic_match(a: str, b: str) -> float:
    if not a or not b or jellyfish is None:
        return 0.0
    try:
        first_a, first_b = a.split()[0], b.split()[0]
        return 1.0 if jellyfish.soundex(first_a) == jellyfish.soundex(first_b) else 0.0
    except Exception:
        return 0.0


def dob_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    # Same year+month (e.g. day transposed/misrecorded across source systems) counts partial.
    a_parts, b_parts = a.split("-"), b.split("-")
    if len(a_parts) == 3 and len(b_parts) == 3 and a_parts[:2] == b_parts[:2]:
        return 0.5
    return 0.0


def address_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return fuzz.token_sort_ratio(a, b) / 100.0


def feature_vector(record_a: Dict[str, str], record_b: Dict[str, str]) -> List[float]:
    return [
        name_similarity(record_a.get("name", ""), record_b.get("name", "")),
        name_phonetic_match(record_a.get("name", ""), record_b.get("name", "")),
        dob_similarity(record_a.get("date_of_birth", ""), record_b.get("date_of_birth", "")),
        address_similarity(record_a.get("address", ""), record_b.get("address", "")),
    ]
