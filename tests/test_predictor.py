from realtime_alpha.bus import FEATURES_OUT, PREDICTIONS_OUT, MemoryBus
from realtime_alpha.core import FeatureWindow, Prediction
from realtime_alpha.prediction.service import run_predictor


async def test_predictor_emits_a_tagged_prediction_per_signalling_strategy():
    bus = MemoryBus()
    fw = FeatureWindow("BTCUSDT", 1, 100.0, {"ema_fast": 101.0, "ema_slow": 100.0})
    await bus.send(FEATURES_OUT, "BTCUSDT", fw.to_dict())

    await run_predictor(bus, ["momentum"], max_records=1)

    preds = bus.history(PREDICTIONS_OUT)
    assert len(preds) == 1
    assert preds[0].key == "BTCUSDT"
    p = Prediction.from_dict(preds[0].value)
    assert p.strategy_id == "momentum"
    assert p.direction == 1


async def test_predictor_skips_strategies_with_no_signal():
    bus = MemoryBus()
    fw = FeatureWindow("BTCUSDT", 1, 100.0, {})  # momentum has no EMAs -> no signal
    await bus.send(FEATURES_OUT, "BTCUSDT", fw.to_dict())

    await run_predictor(bus, ["momentum"], max_records=1)

    assert bus.history(PREDICTIONS_OUT) == []
