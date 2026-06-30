import pytest

from realtime_alpha.core import FeatureWindow
from realtime_alpha.ml.dataset import DEFAULT_FEATURE_COLS
from realtime_alpha.strategies import registered_ids
from realtime_alpha.strategies.ml_model import MLModelStrategy


class _StubModel:
    def __init__(self, p_up: float) -> None:
        self._p = p_up

    def predict_proba(self, x):
        return [[1.0 - self._p, self._p]]


def _fw(price: float = 100.0) -> FeatureWindow:
    return FeatureWindow("BTCUSDT", 1000, price, dict.fromkeys(DEFAULT_FEATURE_COLS, 1.0))


def test_ml_model_emits_signed_prediction_from_proba():
    p = MLModelStrategy(model=_StubModel(0.7), feature_cols=DEFAULT_FEATURE_COLS).predict(_fw())
    assert p is not None
    assert p.strategy_id == "ml_model"
    assert p.yhat > 0
    assert p.confidence == pytest.approx(0.4)  # edge 0.2 -> confidence 0.4
    assert p.ref_price == 100.0 and p.horizon_s == 60


def test_ml_model_bearish_when_proba_below_half():
    p = MLModelStrategy(model=_StubModel(0.3), feature_cols=DEFAULT_FEATURE_COLS).predict(_fw())
    assert p.yhat < 0 and p.confidence == pytest.approx(0.4)


def test_ml_model_inert_without_a_model():
    assert MLModelStrategy().predict(_fw()) is None  # no artifact -> no signal


def test_ml_model_none_on_warmup_missing_features():
    s = MLModelStrategy(model=_StubModel(0.7), feature_cols=DEFAULT_FEATURE_COLS)
    assert s.predict(FeatureWindow("BTCUSDT", 1, 100.0, {"ema_fast": 1.0})) is None


def test_ml_model_is_registered():
    assert "ml_model" in registered_ids()
