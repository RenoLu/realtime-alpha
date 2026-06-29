import pytest

from realtime_alpha.core import FeatureWindow, Prediction
from realtime_alpha.strategies import registered_ids
from realtime_alpha.strategies.ensemble import EnsembleStrategy


def _fw(price: float = 100.0, ts: int = 1000) -> FeatureWindow:
    return FeatureWindow("BTCUSDT", ts, price, {})


def _pred(yhat: float, conf: float, sid: str = "x") -> Prediction:
    return Prediction("BTCUSDT", 60, yhat, conf, sid, ts=1000, ref_price=100.0)


class _Stub:
    def __init__(self, sid: str, pred: Prediction | None) -> None:
        self.id = sid
        self.horizon_s = 60
        self._pred = pred

    def predict(self, fw: FeatureWindow, ctx=None) -> Prediction | None:
        return self._pred


def test_ensemble_blends_children_confidence_weighted():
    s1 = _Stub("a", _pred(0.10, 0.8, "a"))
    s2 = _Stub("b", _pred(-0.02, 0.2, "b"))
    p = EnsembleStrategy(children=[s1, s2]).predict(_fw())
    assert p is not None
    assert p.strategy_id == "ensemble"
    assert p.yhat == pytest.approx(0.076)  # (0.10*0.8 + -0.02*0.2) / (0.8+0.2)
    assert p.confidence == pytest.approx(0.5)  # mean of child confidences
    assert p.ref_price == 100.0


def test_ensemble_drops_none_children():
    s1 = _Stub("a", _pred(0.10, 0.8, "a"))
    s2 = _Stub("b", None)
    p = EnsembleStrategy(children=[s1, s2]).predict(_fw())
    assert p is not None
    assert p.yhat == pytest.approx(0.10)
    assert p.confidence == pytest.approx(0.8)


def test_ensemble_returns_none_when_no_child_signals():
    s1, s2 = _Stub("a", None), _Stub("b", None)
    assert EnsembleStrategy(children=[s1, s2]).predict(_fw()) is None


def test_ensemble_is_registered():
    assert "ensemble" in registered_ids()
