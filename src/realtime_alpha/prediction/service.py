"""The predictor service.

Consumes feature windows from ``features.out``, runs every enabled strategy on each
window, and emits the resulting predictions (tagged with ``strategy_id``) to
``predictions.out``. Strategies that have no signal for a window return ``None`` and are
skipped. Because every prediction carries its ``strategy_id``, the downstream evaluator
can score each strategy independently for the live leaderboard.
"""

from __future__ import annotations

from collections.abc import Callable

from ..bus import FEATURES_OUT, PREDICTIONS_OUT, Bus
from ..core import FeatureWindow, PredictionContext
from ..strategies import enabled_strategies


async def run_predictor(
    bus: Bus,
    strategy_ids: list[str],
    *,
    ctx_provider: Callable[[], PredictionContext] | None = None,
    max_records: int | None = None,
) -> None:
    """Run enabled strategies on each feature window.

    ``ctx_provider`` (optional) is called per window to supply the shared
    ``PredictionContext`` (sentiment/deep caches); strategies that don't need it ignore it.
    """
    strategies = enabled_strategies(strategy_ids)
    processed = 0

    async for rec in bus.stream(FEATURES_OUT):
        fw = FeatureWindow.from_dict(rec.value)
        ctx = ctx_provider() if ctx_provider is not None else None
        for strategy in strategies:
            prediction = strategy.predict(fw, ctx)
            if prediction is not None:
                await bus.send(PREDICTIONS_OUT, fw.symbol, prediction.to_dict())

        processed += 1
        if max_records is not None and processed >= max_records:
            return
