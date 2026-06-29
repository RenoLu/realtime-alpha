"""Map Binance symbols to the identifiers each sentiment connector expects.

StockTwits uses ``BTC.X`` for crypto; Reddit/news search on the asset name.
"""

from __future__ import annotations

SYMBOL_MAP: dict[str, dict[str, str]] = {
    "BTCUSDT": {
        "name": "Bitcoin", "stocktwits": "BTC.X", "reddit": "Bitcoin", "yahoo": "BTC-USD"
    },
    "ETHUSDT": {
        "name": "Ethereum", "stocktwits": "ETH.X", "reddit": "Ethereum", "yahoo": "ETH-USD"
    },
}


def connectors_for(symbol: str) -> dict[str, str] | None:
    """Connector identifiers for ``symbol``, or ``None`` if unmapped."""
    return SYMBOL_MAP.get(symbol)
