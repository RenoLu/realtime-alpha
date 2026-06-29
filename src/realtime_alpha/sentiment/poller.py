"""Background sentiment poller.

Periodically pulls social/news sentiment per symbol via the vendored (sync) connectors,
wrapped in ``asyncio.to_thread`` so they don't block the event loop, aggregates to a
``SentimentSnapshot``, and writes it to the cache. Slow cadence (sentiment moves slowly)
keeps cost/rate-limits bounded; strategies read the cache per window. Fetchers are
injectable for tests; failures are swallowed per source so one dead API can't stall it.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable

from .aggregate import aggregate_sentiment
from .cache import SentimentCache
from .crypto_symbols import connectors_for

Fetcher = Callable[[str], str | None]


def _default_stocktwits(ticker: str) -> str | None:
    from ..dataflows.stocktwits import fetch_stocktwits_messages

    return fetch_stocktwits_messages(ticker)


def _default_reddit(ticker: str) -> str | None:
    from ..dataflows.reddit import fetch_reddit_posts

    return fetch_reddit_posts(ticker)


async def _safe(fetch: Fetcher, arg: str) -> str | None:
    try:
        return await asyncio.to_thread(fetch, arg)
    except Exception:  # noqa: BLE001 - a dead source must not stall the poller
        return None


async def run_sentiment_poller(
    cache: SentimentCache,
    symbols: list[str],
    *,
    interval: float = 45.0,
    stocktwits_fetch: Fetcher | None = None,
    reddit_fetch: Fetcher | None = None,
    now_ms: Callable[[], int] | None = None,
    max_rounds: int | None = None,
) -> None:
    st = stocktwits_fetch or _default_stocktwits
    rd = reddit_fetch or _default_reddit
    clock = now_ms or (lambda: int(time.time() * 1000))
    rounds = 0

    while True:
        for symbol in symbols:
            conn = connectors_for(symbol)
            if conn is None:
                continue
            st_summary = await _safe(st, conn["stocktwits"])
            rd_text = await _safe(rd, conn["reddit"])
            cache.set(
                aggregate_sentiment(
                    symbol, stocktwits_summary=st_summary, reddit_text=rd_text, ts=clock()
                )
            )
        rounds += 1
        if max_rounds is not None and rounds >= max_rounds:
            return
        await asyncio.sleep(interval)
