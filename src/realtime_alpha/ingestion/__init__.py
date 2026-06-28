"""Live market-data ingestion: Binance WebSocket -> normalized ticks -> the bus."""

from __future__ import annotations

from .binance_ws import binance_trade_stream
from .normalize import normalize_binance_trade
from .producer import run_ingestion
from .rest_poll import binance_rest_trade_stream

__all__ = [
    "binance_rest_trade_stream",
    "binance_trade_stream",
    "normalize_binance_trade",
    "run_ingestion",
]
