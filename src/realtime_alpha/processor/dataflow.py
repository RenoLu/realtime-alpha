"""The streaming feature processor.

Consumes raw trades from the bus, keeps one ``FeatureEngine`` per symbol, and emits a
``FeatureWindow`` per trade to ``features.out``. It is bus-agnostic, so the same code
runs over Redpanda (local/Fly) or Kinesis (AWS) via the bus adapter.

``max_records`` bounds the run for tests; production passes ``None`` and runs forever.
"""

from __future__ import annotations

from ..bus import FEATURES_OUT, TRADES_RAW, Bus
from ..core import Tick
from .features import FeatureEngine


async def run_feature_processor(
    bus: Bus,
    *,
    ema_fast: int = 12,
    ema_slow: int = 26,
    rsi_period: int = 14,
    vol_window: int = 20,
    max_records: int | None = None,
) -> None:
    engines: dict[str, FeatureEngine] = {}
    processed = 0

    async for rec in bus.stream(TRADES_RAW):
        tick = Tick.from_dict(rec.value)
        engine = engines.get(tick.symbol)
        if engine is None:
            engine = FeatureEngine(
                tick.symbol,
                ema_fast=ema_fast,
                ema_slow=ema_slow,
                rsi_period=rsi_period,
                vol_window=vol_window,
            )
            engines[tick.symbol] = engine

        fw = engine.update(tick.price, tick.volume, tick.ts)
        await bus.send(FEATURES_OUT, fw.symbol, fw.to_dict())

        processed += 1
        if max_records is not None and processed >= max_records:
            return
