import asyncio

from realtime_alpha.bus import FEATURES_OUT, PREDICTIONS_OUT, SCORES_OUT, MemoryBus
from realtime_alpha.core import FeatureWindow, Outcome, Prediction
from realtime_alpha.evaluation.evaluator import OutcomeJoiner, run_evaluator


def _pred(strategy="momentum", horizon=60, yhat=0.01, ref=100.0, ts=1000) -> Prediction:
    return Prediction("BTCUSDT", horizon, yhat, 0.6, strategy, ts=ts, ref_price=ref)


# --- the pure join logic -------------------------------------------------------------

def test_joiner_scores_only_after_horizon_elapses():
    j = OutcomeJoiner()
    j.add_prediction(_pred(ts=1000, horizon=60))  # target_ts = 61_000
    assert j.observe_price("BTCUSDT", 101.0, ts=30_000) == []  # not matured yet
    outs = j.observe_price("BTCUSDT", 102.0, ts=61_000)  # matured
    assert len(outs) == 1
    assert outs[0].realized_price == 102.0 and outs[0].scored_ts == 61_000
    assert outs[0].realized_return == 0.02 and outs[0].hit is True
    assert j.pending_count == 0  # consumed once scored


def test_joiner_ignores_other_symbols():
    j = OutcomeJoiner()
    j.add_prediction(_pred(ts=1000))
    assert j.observe_price("ETHUSDT", 200.0, ts=10_000_000) == []
    assert j.pending_count == 1


def test_joiner_matures_due_predictions_and_keeps_the_rest():
    j = OutcomeJoiner()
    j.add_prediction(_pred(horizon=60, ts=1000))  # target 61_000
    j.add_prediction(_pred(horizon=3600, ts=1000))  # target 3_601_000
    outs = j.observe_price("BTCUSDT", 101.0, ts=61_000)
    assert [o.horizon_s for o in outs] == [60]
    assert j.pending_count == 1  # the 1h prediction is still pending


# --- the bus wiring ------------------------------------------------------------------

async def test_run_evaluator_emits_scored_outcome_to_scores_topic():
    bus = MemoryBus()
    await bus.send(
        PREDICTIONS_OUT, "BTCUSDT", _pred(ts=1000, yhat=0.01, ref=100.0).to_dict()
    )
    await bus.send(FEATURES_OUT, "BTCUSDT", FeatureWindow("BTCUSDT", 30_000, 100.5, {}).to_dict())
    await bus.send(FEATURES_OUT, "BTCUSDT", FeatureWindow("BTCUSDT", 61_000, 102.0, {}).to_dict())

    await asyncio.wait_for(run_evaluator(bus, max_scores=1), timeout=2.0)

    scores = bus.history(SCORES_OUT)
    assert len(scores) == 1
    o = Outcome.from_dict(scores[0].value)
    assert o.strategy_id == "momentum" and o.hit is True and o.realized_price == 102.0
