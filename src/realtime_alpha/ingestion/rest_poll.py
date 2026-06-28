"""Real-data REST polling source (fallback when exchange WebSockets are unreachable).

Some networks block the exchange WS port (Binance.US WS is on :9443); REST is on :443.
This source polls ``/api/v3/trades`` and yields **real** recent trades in the same shape
as the WS source, so the producer and normalizer don't care which one feeds them. It is
NOT a synthetic generator — the data is real market activity, just pulled over HTTPS.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import httpx

BINANCE_US_REST = "https://api.binance.us"


def binance_rest_to_payload(symbol: str, trade: dict[str, Any]) -> dict[str, Any]:
    """Map a Binance REST trade to the WS ``@trade`` payload shape."""
    return {
        "s": symbol,
        "t": trade["id"],
        "p": trade["price"],
        "q": trade["qty"],
        "T": trade["time"],
    }


async def binance_rest_trade_stream(
    symbols: list[str],
    *,
    base_url: str = BINANCE_US_REST,
    poll_interval: float = 1.0,
    limit: int = 100,
    client: httpx.AsyncClient | None = None,
) -> AsyncIterator[dict[str, Any]]:
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=10.0)
    last_id: dict[str, int] = dict.fromkeys(symbols, 0)
    try:
        while True:
            for symbol in symbols:
                resp = await client.get(
                    f"{base_url}/api/v3/trades", params={"symbol": symbol, "limit": limit}
                )
                resp.raise_for_status()
                for trade in resp.json():  # ascending by id
                    if trade["id"] <= last_id[symbol]:
                        continue
                    last_id[symbol] = trade["id"]
                    yield binance_rest_to_payload(symbol, trade)
            await asyncio.sleep(poll_interval)
    finally:
        if owns_client:
            await client.aclose()
