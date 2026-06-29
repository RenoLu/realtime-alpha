import pytest

from realtime_alpha.core import Prediction
from realtime_alpha.evaluation.metrics import (
    calibration_gap,
    directional_accuracy,
    mae,
    mean_confidence,
    score_prediction,
)


def _pred(yhat: float, conf: float = 0.6, ref: float = 100.0) -> Prediction:
    return Prediction("BTCUSDT", 60, yhat, conf, "momentum", ts=1000, ref_price=ref)


def test_score_prediction_computes_realized_return_and_hit():
    o = score_prediction(_pred(0.01), realized_price=101.0, scored_ts=61000)
    assert o.realized_return == pytest.approx(0.01)  # (101-100)/100
    assert o.hit is True  # predicted up, went up
    assert o.abs_error == pytest.approx(0.0)
    assert o.scored_ts == 61000 and o.pred_ts == 1000
    assert o.strategy_id == "momentum" and o.realized_price == 101.0


def test_score_prediction_directional_miss():
    o = score_prediction(_pred(0.01), realized_price=99.0, scored_ts=1)  # up call, went down
    assert o.realized_return == pytest.approx(-0.01)
    assert o.hit is False
    assert o.abs_error == pytest.approx(0.02)


def test_score_prediction_zero_ref_price_is_safe():
    o = score_prediction(_pred(0.01, ref=0.0), realized_price=100.0, scored_ts=1)
    assert o.realized_return == 0.0  # no division by zero


def test_aggregate_metrics_over_outcomes():
    outs = [
        score_prediction(_pred(0.01, conf=0.8), 101.0, 1),  # hit, err 0
        score_prediction(_pred(0.01, conf=0.4), 99.0, 1),  # miss, err 0.02
        score_prediction(_pred(-0.01, conf=0.6), 99.0, 1),  # hit, err 0
    ]
    assert directional_accuracy(outs) == pytest.approx(2 / 3)
    assert mae(outs) == pytest.approx(0.02 / 3)
    assert mean_confidence(outs) == pytest.approx((0.8 + 0.4 + 0.6) / 3)
    assert calibration_gap(outs) == pytest.approx(mean_confidence(outs) - 2 / 3)


def test_empty_metrics_are_zero():
    assert directional_accuracy([]) == 0.0
    assert mae([]) == 0.0
    assert mean_confidence([]) == 0.0
    assert calibration_gap([]) == 0.0
