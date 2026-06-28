"""Ingestion producer: real exchange trades -> normalized ticks -> the bus.

``source`` is any async iterable of Binance ``@trade`` payloads — the live WebSocket
client in production, a list-backed iterator in tests. Trades are de-duplicated by
ascending trade id per symbol (WS reconnects can replay), then produced to ``trades.raw``
keyed by symbol.
"""

from __future__ import annotations

from collections.abc import AsyncIterable
from typing import Any

from ..bus import TRADES_RAW, Bus
from .normalize import normalize_binance_trade


async def run_ingestion(
    bus: Bus,
    source: AsyncIterable[dict[str, Any]],
    *,
    max_records: int | None = None,
) -> None:
    last_trade_id: dict[str, int] = {}
    produced = 0

    async for data in source:
        symbol = data["s"]
        trade_id = int(data["t"])
        if last_trade_id.get(symbol, -1) >= trade_id:
            continue  # already seen this (or an older) trade for the symbol
        last_trade_id[symbol] = trade_id

        tick = normalize_binance_trade(data)
        await bus.send(TRADES_RAW, tick.symbol, tick.to_dict())

        produced += 1
        if max_records is not None and produced >= max_records:
            return
