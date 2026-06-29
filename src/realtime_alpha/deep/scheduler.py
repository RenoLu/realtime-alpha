"""Slow scheduler that refreshes each symbol's DeepView off the hot path.

Runs the analyst chain per symbol on a long cadence (default hourly), writes the standing
view to the cache (read per-window by the ``deep_analysis`` strategy), and notifies
``on_view`` so the server can broadcast the briefing. The blocking LLM calls + context
gathering run in threads so the event loop stays responsive; a failure on one symbol is
isolated and the loop continues.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable

from ..core import DeepView
from ..llm import HAIKU, OPUS, ModelClient
from .analyst import DeepContext, analyze_symbol
from .cache import DeepViewCache


async def run_deep_analysis(
    cache: DeepViewCache,
    symbols: list[str],
    *,
    client: ModelClient,
    context_provider: Callable[[str], DeepContext],
    now_ms: Callable[[], int] | None = None,
    horizon_s: int = 3600,
    quick_model: str = HAIKU,
    deep_model: str = OPUS,
    interval: float = 3600.0,
    max_rounds: int | None = None,
    on_view: Callable[[DeepView], None] | None = None,
) -> None:
    clock = now_ms or (lambda: int(time.time() * 1000))
    rounds = 0

    while True:
        for symbol in symbols:
            try:
                ctx = await asyncio.to_thread(context_provider, symbol)
                view = await asyncio.to_thread(
                    analyze_symbol,
                    symbol,
                    ctx,
                    client=client,
                    ts=clock(),
                    horizon_s=horizon_s,
                    quick_model=quick_model,
                    deep_model=deep_model,
                )
            except Exception:  # noqa: BLE001 - one bad symbol must not kill the scheduler
                continue
            cache.set(view)
            if on_view is not None:
                on_view(view)
        rounds += 1
        if max_rounds is not None and rounds >= max_rounds:
            return
        await asyncio.sleep(interval)
