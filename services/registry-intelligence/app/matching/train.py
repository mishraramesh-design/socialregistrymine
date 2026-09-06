"""Trains the base entity-resolution model on synthetic data.

There is no real state data to train on yet (per docs/architecture.md's matching
strategy: the base model has to work on day one, before any client's data exists).
This generates synthetic "same person, re-entered by a different department" pairs
(typo'd names, reformatted addresses, occasional DOB transcription slips) as
positives, and both random and adversarial "different person" pairs as negatives,
then fits a small logistic regression on the four features in features.py.

Run: `python -m app.matching.train` from the service root. Writes model.joblib
next to this file. Re-run whenever features.py changes, or once real
deterministic-match weak-labels are available from a live deployment (see
docs/architecture.md's fine-tuning note — that's a different, later training
loop, not this script).
"""

import random
from pathlib import Path

import joblib
import numpy as np
from faker import Faker
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split

from .features import feature_vector

MODEL_PATH = Path(__file__).parent / "model.joblib"


def _typo(name: str, rng: random.Random) -> str:
    """Simulates re-entry noise: dropped char, swapped adjacent chars, or an initial."""
    if not name or rng.random() < 0.3:
        return name
    parts = name.split()
    choice = rng.random()
    if choice < 0.34 and len(parts) > 1:
        # First name -> initial (e.g. "Anita Devi" -> "A. Devi")
        return f"{parts[0][0]}. " + " ".join(parts[1:])
    word = rng.choice(parts)
    idx = rng.randrange(len(word))
    if choice < 0.67 and len(word) > 1:
        noisy = word[:idx] + word[idx + 1 :]  # dropped char
    elif len(word) > 2:
        j = min(idx + 1, len(word) - 1)
        chars = list(word)
        chars[idx], chars[j] = chars[j], chars[idx]  # swapped chars
        noisy = "".join(chars)
    else:
        noisy = word
    return name.replace(word, noisy, 1)


def _reformat_address(address: str, rng: random.Random) -> str:
    if rng.random() < 0.4:
        return address
    tokens = address.split(",")
    rng.shuffle(tokens)
    return ",".join(t.strip() for t in tokens)


def _drop_fields_a_real_source_might_lack(record: dict, rng: random.Random) -> dict:
    """A source system frequently doesn't collect every canonical field — an
    income-tax record rarely carries a home address, some land records predate
    DOB capture. The model has to recognize a match on name+DOB alone when the
    other side never supplied an address at all — not seeing this pattern in
    training was a real bug (missing fields scored as "actively different"
    rather than "no signal"; see features.py's NEUTRAL constant)."""
    record = dict(record)
    if rng.random() < 0.25:
        record["address"] = ""
    if rng.random() < 0.08:
        record["date_of_birth"] = ""
    return record


def _generate_identity(fake: Faker) -> dict:
    return {
        "name": fake.name(),
        "date_of_birth": fake.date_of_birth(minimum_age=1, maximum_age=95).isoformat(),
        "address": f"{fake.building_number()} {fake.street_name()}, {fake.city()}, {fake.postcode()}",
    }


def generate_dataset(n_pairs: int = 2500, seed: int = 42):
    rng = random.Random(seed)
    fake = Faker()
    Faker.seed(seed)

    X, y = [], []
    identities = [_generate_identity(fake) for _ in range(n_pairs)]

    for identity in identities:
        # Positive: same person, re-entered with plausible noise by another source system.
        duplicate = {
            "name": _typo(identity["name"], rng),
            "date_of_birth": identity["date_of_birth"]
            if rng.random() > 0.05
            else identity["date_of_birth"][:7] + "-01",  # rare day-transcription slip
            "address": _reformat_address(identity["address"], rng),
        }
        duplicate = _drop_fields_a_real_source_might_lack(duplicate, rng)
        X.append(feature_vector(identity, duplicate))
        y.append(1)

        # Negative: unrelated person.
        other = rng.choice(identities)
        X.append(feature_vector(identity, other))
        y.append(0)

        # Hard negative: same household address, different person (e.g. family members).
        hard_negative = _generate_identity(fake)
        hard_negative["address"] = identity["address"]
        X.append(feature_vector(identity, hard_negative))
        y.append(0)

    return np.array(X), np.array(y)


def train():
    X, y = generate_dataset()
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    model = LogisticRegression(class_weight="balanced")
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    print(classification_report(y_test, preds, target_names=["no_match", "match"]))

    joblib.dump(model, MODEL_PATH)
    print(f"Saved model to {MODEL_PATH}")


if __name__ == "__main__":
    train()
