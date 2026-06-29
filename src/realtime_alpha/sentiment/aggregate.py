"""Aggregate connector output into a numeric SentimentSnapshot.

Pure function (no IO) so the scoring is unit-testable. StockTwits' user-labeled
bull/bear counts give a clean signed score in [-1, 1]; other connectors (Reddit, news)
contribute context and are recorded as ``sources``.
"""

from __future__ import annotations

import re

from ..core import SentimentSnapshot

_BULL = re.compile(r"Bullish:\s*(\d+)")
_BEAR = re.compile(r"Bearish:\s*(\d+)")


def _parse_stocktwits(summary: str) -> tuple[int, int]:
    bull = _BULL.search(summary)
    bear = _BEAR.search(summary)
    return (int(bull.group(1)) if bull else 0, int(bear.group(1)) if bear else 0)


def aggregate_sentiment(
    symbol: str,
    *,
    stocktwits_summary: str | None = None,
    reddit_text: str | None = None,
    ts: int,
) -> SentimentSnapshot:
    bull, bear = _parse_stocktwits(stocktwits_summary or "")
    n = bull + bear
    score = round((bull - bear) / n, 4) if n else 0.0
    sources = tuple(
        name
        for name, present in (
            ("stocktwits", bool(stocktwits_summary)),
            ("reddit", bool(reddit_text)),
        )
        if present
    )
    return SentimentSnapshot(symbol=symbol, score=score, n=n, ts=ts, sources=sources)
