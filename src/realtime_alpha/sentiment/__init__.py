"""Social/news sentiment: a slow background poller + per-symbol cache.

Bridges the batch connectors (vendored from TradingAgents) to the streaming predictor:
the poller refreshes a ``SentimentSnapshot`` per symbol on a slow cadence, and strategies
read the cache per window via ``PredictionContext``.
"""

from __future__ import annotations

from .aggregate import aggregate_sentiment
from .cache import SentimentCache
from .crypto_symbols import SYMBOL_MAP, connectors_for
from .poller import run_sentiment_poller

__all__ = [
    "SYMBOL_MAP",
    "SentimentCache",
    "aggregate_sentiment",
    "connectors_for",
    "run_sentiment_poller",
]
