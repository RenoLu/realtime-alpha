"""Normalize exchange payloads into the platform's ``Tick`` type."""

from __future__ import annotations

from typing import Any

from ..core import Tick


def normalize_binance_trade(data: dict[str, Any]) -> Tick:
    """Map a Binance ``@trade`` payload to a ``Tick``.

    Fields: ``s`` symbol, ``p`` price (string), ``q`` quantity (string), ``T`` trade
    time in epoch ms.
    """
    return Tick(
        symbol=data["s"],
        price=float(data["p"]),
        volume=float(data["q"]),
        ts=int(data["T"]),
    )
