import asyncio

import pytest

from realtime_alpha.bus import SCORES_OUT, MemoryBus
from realtime_alpha.core import Outcome
from realtime_alpha.lakehouse.parquet import LocalWriter
from realtime_alpha.lakehouse.query import accuracy_by_strategy, connect
from realtime_alpha.lakehouse.sink import run_lakehouse_sink


async def _write_outcomes(tmp_path):
    bus = MemoryBus()
    rows = [("momentum", True), ("momentum", True), ("momentum", False), ("sentiment_llm", True)]
    for i, (strat, hit) in enumerate(rows):
        o = Outcome(
            "BTCUSDT", strat, 60, 0.01, 0.01 if hit else -0.01, hit,
            0.0 if hit else 0.02, 0.6, 100.0, 101.0, 1000, 60000 + i,
        )
        await bus.send(SCORES_OUT, "BTCUSDT", o.to_dict())
    await asyncio.wait_for(
        run_lakehouse_sink(bus, LocalWriter(tmp_path), batch_size=10, max_records=4), timeout=3
    )


async def test_accuracy_by_strategy_over_local_parquet(tmp_path):
    await _write_outcomes(tmp_path)
    rows = accuracy_by_strategy(connect(), tmp_path.as_posix())
    by = {r["strategy_id"]: r for r in rows}
    assert by["momentum"]["n"] == 3
    assert by["momentum"]["dir_acc"] == pytest.approx(2 / 3)
    assert by["sentiment_llm"]["dir_acc"] == 1.0
    assert rows[0]["strategy_id"] == "sentiment_llm"  # ranked by accuracy desc
