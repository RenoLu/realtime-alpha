"""Wire the shared caches into the contexts the strategies and deep scheduler read.

- ``FeatureCache`` + ``run_feature_tap``: keep the latest feature window per symbol (so the
  off-path deep scheduler can summarize current market state without touching the hot path).
- ``make_prediction_ctx_provider``: snapshot the sentiment + deep caches into a
  ``PredictionContext`` each window (passed to ``run_predictor``).
- ``make_deep_context_provider``: assemble a ``DeepContext`` per symbol for the analyst chain.
"""

from __future__ import annotations

from collections.abc import Callable

from ..bus import FEATURES_OUT, Bus
from ..core import FeatureWindow, PredictionContext
from ..deep import DeepContext


class FeatureCache:
    def __init__(self) -> None:
        self._fws: dict[str, FeatureWindow] = {}

    def set(self, fw: FeatureWindow) -> None:
        self._fws[fw.symbol] = fw

    def get(self, symbol: str) -> FeatureWindow | None:
        return self._fws.get(symbol)

    def snapshot(self) -> dict[str, FeatureWindow]:
        return dict(self._fws)


async def run_feature_tap(
    bus: Bus, cache: FeatureCache, *, max_records: int | None = None
) -> None:
    """Mirror the latest feature window per symbol into ``cache`` off the predictor path."""
    seen = 0
    async for rec in bus.stream(FEATURES_OUT):
        cache.set(FeatureWindow.from_dict(rec.value))
        seen += 1
        if max_records is not None and seen >= max_records:
            return


def summarize_features(fw: FeatureWindow) -> str:
    """A compact, human-readable one-liner of the current features (for LLM prompts)."""
    f = fw.features
    parts = [f"last {fw.last_price:.2f}"]
    if "ret_1" in f:
        parts.append(f"ret_1 {f['ret_1'] * 100:+.2f}%")
    if "rsi" in f:
        parts.append(f"rsi {f['rsi']:.0f}")
    if "ema_fast" in f and f.get("ema_slow"):
        spread = (f["ema_fast"] - f["ema_slow"]) / f["ema_slow"]
        parts.append(f"ema_spread {spread:+.4f}")
    if "vol" in f:
        parts.append(f"vol {f['vol']:.5f}")
    return ", ".join(parts)


def make_prediction_ctx_provider(
    *, sentiment_cache: object | None = None, deep_cache: object | None = None
) -> Callable[[], PredictionContext]:
    def provider() -> PredictionContext:
        return PredictionContext(
            sentiment=sentiment_cache.snapshot() if sentiment_cache is not None else {},
            deep=deep_cache.snapshot() if deep_cache is not None else {},
        )

    return provider


def make_deep_context_provider(
    *,
    feature_cache: FeatureCache | None = None,
    sentiment_cache: object | None = None,
    news_fetch: Callable[[str], str | None] | None = None,
) -> Callable[[str], DeepContext]:
    def provider(symbol: str) -> DeepContext:
        fw = feature_cache.get(symbol) if feature_cache is not None else None
        price_summary = summarize_features(fw) if fw is not None else "no recent market data"
        sentiment = sentiment_cache.get(symbol) if sentiment_cache is not None else None
        news = ""
        if news_fetch is not None:
            try:
                news = news_fetch(symbol) or ""
            except Exception:  # noqa: BLE001 - news is best-effort; never block the analysis
                news = ""
        return DeepContext(
            symbol=symbol, price_summary=price_summary, sentiment=sentiment, news=news
        )

    return provider
