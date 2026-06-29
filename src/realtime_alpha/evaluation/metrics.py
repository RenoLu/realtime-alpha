"""Pure scoring math: a prediction + its realized price -> an Outcome, and aggregates."""

from __future__ import annotations

from collections.abc import Sequence

from ..core import Outcome, Prediction


def _sign(x: float) -> int:
    return (x > 0) - (x < 0)


def score_prediction(pred: Prediction, realized_price: float, scored_ts: int) -> Outcome:
    """Score ``pred`` against the price realized once its horizon elapsed."""
    realized_return = (realized_price - pred.ref_price) / pred.ref_price if pred.ref_price else 0.0
    return Outcome(
        symbol=pred.symbol,
        strategy_id=pred.strategy_id,
        horizon_s=pred.horizon_s,
        yhat=pred.yhat,
        realized_return=realized_return,
        hit=_sign(pred.yhat) == _sign(realized_return),
        abs_error=abs(pred.yhat - realized_return),
        confidence=pred.confidence,
        ref_price=pred.ref_price,
        realized_price=realized_price,
        pred_ts=pred.ts,
        scored_ts=scored_ts,
        model_ver=pred.model_ver,
    )


def directional_accuracy(outcomes: Sequence[Outcome]) -> float:
    return sum(o.hit for o in outcomes) / len(outcomes) if outcomes else 0.0


def mae(outcomes: Sequence[Outcome]) -> float:
    return sum(o.abs_error for o in outcomes) / len(outcomes) if outcomes else 0.0


def mean_confidence(outcomes: Sequence[Outcome]) -> float:
    return sum(o.confidence for o in outcomes) / len(outcomes) if outcomes else 0.0


def calibration_gap(outcomes: Sequence[Outcome]) -> float:
    """mean_confidence - dir_acc; positive = the strategy is over-confident."""
    return mean_confidence(outcomes) - directional_accuracy(outcomes)
