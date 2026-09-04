"""Loads the trained base entity-resolution model for scoring record pairs.

Falls back to a fixed-weight heuristic over the same features if model.joblib
hasn't been trained yet (e.g. a fresh checkout before running `train.py`) — so
the service is never hard-down for lack of a model file, it just runs with an
untuned baseline until someone trains one.
"""

import logging
from pathlib import Path
from typing import Dict

from .features import feature_vector

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).parent / "model.joblib"

_model = None
_model_load_attempted = False


def _load_model():
    global _model, _model_load_attempted
    if _model_load_attempted:
        return _model
    _model_load_attempted = True
    if MODEL_PATH.exists():
        import joblib

        _model = joblib.load(MODEL_PATH)
        logger.info("Loaded trained entity-resolution model from %s", MODEL_PATH)
    else:
        logger.warning(
            "No trained model at %s — using untuned heuristic weights. Run "
            "`python -m app.matching.train` to train one.",
            MODEL_PATH,
        )
    return _model


# Untrained fallback: equal-ish weighting favoring name+DOB agreement, matching
# the same four features the trained model uses so scores stay comparable.
_FALLBACK_WEIGHTS = [0.35, 0.15, 0.3, 0.2]


def score_pair(record_a: Dict[str, str], record_b: Dict[str, str]) -> float:
    """Returns a match probability in [0, 1] for two canonical-schema records."""
    features = feature_vector(record_a, record_b)
    model = _load_model()
    if model is not None:
        return float(model.predict_proba([features])[0][1])
    return float(sum(w * f for w, f in zip(_FALLBACK_WEIGHTS, features)))
