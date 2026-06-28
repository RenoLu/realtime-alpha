import bytewax.operators as op
import pytest
from bytewax.dataflow import Dataflow
from bytewax.testing import TestingSink, TestingSource, run_main

from realtime_alpha.core import FeatureWindow, Tick
from realtime_alpha.processor.bytewax_flow import feature_pipeline

CFG = {"ema_fast": 2, "ema_slow": 4, "rsi_period": 3, "vol_window": 2}


def _run(ticks: list[Tick]) -> list[tuple[str, FeatureWindow]]:
    """Drive the pipeline with Bytewax's in-memory testing source/sink (no broker)."""
    flow = Dataflow("test")
    inp = op.input("in", flow, TestingSource(ticks))
    feats = feature_pipeline(inp, feature_cfg=CFG)
    captured: list[tuple[str, FeatureWindow]] = []
    op.output("out", feats, TestingSink(captured))
    run_main(flow)
    return captured


def test_pipeline_emits_one_keyed_feature_window_per_tick():
    out = _run([Tick("BTCUSDT", 100.0, 1.0, 1), Tick("BTCUSDT", 110.0, 1.0, 2)])
    assert [key for key, _ in out] == ["BTCUSDT", "BTCUSDT"]
    last_key, last_fw = out[-1]
    assert isinstance(last_fw, FeatureWindow)
    assert last_fw.last_price == 110.0
    assert last_fw.features["ema_fast"] == pytest.approx(106.6666667)  # 2/3*110 + 1/3*100


def test_pipeline_keeps_per_symbol_state_independent():
    out = _run(
        [
            Tick("BTCUSDT", 100.0, 1.0, 1),
            Tick("ETHUSDT", 50.0, 1.0, 1),
            Tick("BTCUSDT", 110.0, 1.0, 2),
        ]
    )
    by_symbol: dict[str, list[FeatureWindow]] = {}
    for key, fw in out:
        by_symbol.setdefault(key, []).append(fw)

    assert by_symbol["ETHUSDT"][-1].features["ema_fast"] == 50.0  # seeded independently
    assert by_symbol["BTCUSDT"][-1].features["ema_fast"] == pytest.approx(106.6666667)
