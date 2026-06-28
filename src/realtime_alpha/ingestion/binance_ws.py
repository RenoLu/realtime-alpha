"""Live Binance.US trade WebSocket source.

Yields the ``data`` object of each combined-stream ``@trade`` message — exactly the shape
``run_ingestion`` expects. Real, keyless, 24/7 market data; no synthetic fallback feeds
the product (a synthetic generator exists only for tests).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import websockets

BINANCE_US_STREAM = "wss://stream.binance.us:9443/stream"


async def binance_trade_stream(
    symbols: list[str],
    *,
    url_base: str = BINANCE_US_STREAM,
) -> AsyncIterator[dict[str, Any]]:
    streams = "/".join(f"{s.lower()}@trade" for s in symbols)
    url = f"{url_base}?streams={streams}"
    async with websockets.connect(url, ping_interval=20) as ws:
        async for raw in ws:
            msg = json.loads(raw)
            # Combined-stream envelope: {"stream": "...", "data": {...}}
            yield msg.get("data", msg)
