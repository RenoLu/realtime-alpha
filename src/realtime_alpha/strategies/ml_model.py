"""ml_model: a trained classifier served as a Strategy.

Loads a walk-forward-trained model (see ``ml/train.py``) and turns its up-probability into a
signed forecast: ``yhat`` from the edge over 0.5, ``confidence`` from its magnitude. With no
artifact it's inert (returns None), so it ships in the default lineup harmlessly until a
model is trained; set ``RTA_MODEL_PATH`` (or pass ``model``/``model_path``) to activate it.
Train- and serve-time features are identical (same FeatureEngine), so the vector lines up.
"""

from __future__ import annotations

import os
import warnings
from pathlib import Path
from typing import Any

from ..core import FeatureWindow, Prediction, PredictionContext
from ..ml.dataset import DEFAULT_FEATURE_COLS, features_to_vector
from .registry import register

_YHAT_SCALE = 0.01  # full conviction (prob 0/1) maps to a +/-1% expected return


@register
class MLModelStrategy:
    id = "ml_model"

    def __init__(
        self,
        model: Any = None,
        feature_cols: list[str] | tuple[str, ...] | None = None,
        *,
        model_path: str | None = None,
        horizon_s: int = 60,
        model_ver: str = "ml-v0",
    ) -> None:
        self.horizon_s = horizon_s
        self._model_ver = model_ver
        if model is None:
            path = model_path or os.getenv("RTA_MODEL_PATH")
            if path and Path(path).exists():
                model, feature_cols, self._model_ver = load_artifact(path)
        self._model = model
        self._cols = list(feature_cols) if feature_cols else list(DEFAULT_FEATURE_COLS)

    def predict(
        self, fw: FeatureWindow, ctx: PredictionContext | None = None
    ) -> Prediction | None:
        if self._model is None or any(c not in fw.features for c in self._cols):
            return None  # no artifact, or a warmup window missing features
        vector = [features_to_vector(fw.features, self._cols)]
        with warnings.catch_warnings():
            # LightGBM's sklearn wrapper warns about feature names on a bare list; benign,
            # and silenced here so it doesn't spam once per prediction on the hot path.
            warnings.simplefilter("ignore")
            p_up = float(self._model.predict_proba(vector)[0][1])
        edge = p_up - 0.5
        return Prediction(
            symbol=fw.symbol,
            horizon_s=self.horizon_s,
            yhat=edge * 2 * _YHAT_SCALE,
            confidence=min(1.0, abs(edge) * 2),
            strategy_id=self.id,
            ts=fw.ts,
            model_ver=self._model_ver,
            ref_price=fw.last_price,
        )


def load_artifact(path: str) -> tuple[Any, list[str], str]:
    """Load a (model, feature_cols, model_ver) artifact written by our own trainer.

    Pickle is the standard sklearn/LightGBM persistence format. This only ever loads a
    *local artifact we produced* (``ml/train.py`` -> ``models/``), never untrusted input,
    so arbitrary-code-execution on unpickle is not a concern here.
    """
    import pickle  # noqa: S403 - trusted, self-produced artifact (see docstring)

    with open(path, "rb") as f:
        art = pickle.load(f)  # noqa: S301 - trusted, self-produced artifact
    return art["model"], art["feature_cols"], art.get("model_ver", "ml-v0")
