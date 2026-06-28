import pytest

from realtime_alpha.bus import FEATURES_OUT, TRADES_RAW, MemoryBus
from realtime_alpha.core import FeatureWindow, Tick
from realtime_alpha.processor.dataflow import run_feature_processor

CFG = {"ema_fast": 2, "ema_slow": 4, "rsi_period": 3, "vol_window": 2}


async def test_processor_emits_one_feature_window_per_trade_keyed_by_symbol():
    bus = MemoryBus()
    for i, price in enumerate((100.0, 110.0, 121.0)):
        await bus.send(TRADES_RAW, "BTCUSDT", Tick("BTCUSDT", price, 1.0, ts=i).to_dict())

    await run_feature_processor(bus, max_records=3, **CFG)

    feats = bus.history(FEATURES_OUT)
    assert len(feats) == 3
    assert all(r.key == "BTCUSDT" for r in feats)
    last = FeatureWindow.from_dict(feats[-1].value)
    assert last.last_price == 121.0
    assert last.features["vol"] == pytest.approx(0.0, abs=1e-12)  # two equal +0.1 returns


async def test_processor_keeps_per_symbol_state_independent():
    bus = MemoryBus()
    await bus.send(TRADES_RAW, "BTCUSDT", Tick("BTCUSDT", 100.0, 1.0, 1).to_dict())
    await bus.send(TRADES_RAW, "ETHUSDT", Tick("ETHUSDT", 50.0, 1.0, 1).to_dict())
    await bus.send(TRADES_RAW, "BTCUSDT", Tick("BTCUSDT", 110.0, 1.0, 2).to_dict())

    await run_feature_processor(bus, max_records=3, **CFG)

    feats = [FeatureWindow.from_dict(r.value) for r in bus.history(FEATURES_OUT)]
    eth = next(f for f in feats if f.symbol == "ETHUSDT")
    btc_last = [f for f in feats if f.symbol == "BTCUSDT"][-1]
    assert eth.features["ema_fast"] == 50.0  # seeded independently
    assert btc_last.features["ema_fast"] == pytest.approx(106.6666667)  # 2/3*110 + 1/3*100
