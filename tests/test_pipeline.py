"""Broker-free integration: ticks -> feature processor -> predictor -> predictions.

Composes the independently-tested units over the in-memory bus to prove the full
data->prediction loop wires together end to end.
"""

from realtime_alpha.bus import PREDICTIONS_OUT, TRADES_RAW, MemoryBus
from realtime_alpha.core import Prediction, Tick
from realtime_alpha.prediction import run_predictor
from realtime_alpha.processor import run_feature_processor


async def test_rising_ticks_flow_through_to_bullish_momentum_predictions():
    bus = MemoryBus()
    prices = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0]
    for i, px in enumerate(prices):
        await bus.send(TRADES_RAW, "BTCUSDT", Tick("BTCUSDT", px, 1.0, ts=i).to_dict())

    await run_feature_processor(
        bus, ema_fast=2, ema_slow=4, rsi_period=3, vol_window=3, max_records=len(prices)
    )
    await run_predictor(bus, ["momentum"], max_records=len(prices))

    preds = [Prediction.from_dict(r.value) for r in bus.history(PREDICTIONS_OUT)]
    assert len(preds) == len(prices)  # momentum signals on every window
    assert all(p.strategy_id == "momentum" for p in preds)
    assert preds[-1].direction == 1  # sustained uptrend -> fast EMA leads slow -> bullish
