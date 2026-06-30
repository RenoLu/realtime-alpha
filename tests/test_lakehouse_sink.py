import asyncio

import polars as pl

from realtime_alpha.bus import FEATURES_OUT, SCORES_OUT, MemoryBus
from realtime_alpha.core import FeatureWindow, Outcome
from realtime_alpha.lakehouse.parquet import LocalWriter
from realtime_alpha.lakehouse.sink import run_lakehouse_sink


async def test_sink_writes_partitioned_parquet(tmp_path):
    bus = MemoryBus()
    for i in range(3):
        o = Outcome("BTCUSDT", "momentum", 60, 0.01, 0.01, True, 0.0, 0.6, 100.0, 101.0, 1000, 60000 + i)
        await bus.send(SCORES_OUT, "BTCUSDT", o.to_dict())

    await asyncio.wait_for(
        run_lakehouse_sink(bus, LocalWriter(tmp_path), batch_size=10, flush_interval=0.05, max_records=3),
        timeout=3,
    )

    files = list(tmp_path.glob("outcomes/dt=*/symbol=BTCUSDT/*.parquet"))
    assert len(files) >= 1
    df = pl.read_parquet(files[0])
    assert df.height == 3 and set(df["strategy_id"]) == {"momentum"}


async def test_sink_flattens_feature_records(tmp_path):
    bus = MemoryBus()
    fw = FeatureWindow("BTCUSDT", 0, 100.0, {"ema_fast": 101.0, "rsi": 55.0})
    await bus.send(FEATURES_OUT, "BTCUSDT", fw.to_dict())

    await asyncio.wait_for(
        run_lakehouse_sink(bus, LocalWriter(tmp_path), batch_size=1, max_records=1),
        timeout=3,
    )

    df = pl.read_parquet(next(tmp_path.glob("features/**/*.parquet")))
    assert "ema_fast" in df.columns and "features" not in df.columns  # nested dict flattened
