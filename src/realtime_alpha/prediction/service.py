"""The predictor service.

Consumes feature windows from ``features.out``, runs every enabled strategy on each
window, and emits the resulting predictions (tagged with ``strategy_id``) to
``predictions.out``. Strategies that have no signal for a window return ``None`` and are
skipped. Because every prediction carries its ``strategy_id``, the downstream evaluator
can score each strategy independently for the live leaderboard.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence

from ..bus import FEATURES_OUT, PREDICTIONS_OUT, Bus
from ..core import FeatureWindow, Prediction, PredictionContext
from ..strategies import Strategy, enabled_strategies


def predict_all(
    strategies: Sequence[Strategy],
    fw: FeatureWindow,
    ctx: PredictionContext | None,
) -> list[Prediction]:
    """Run every strategy on one window, isolating failures.

    A strategy that raises (e.g. an LLM call fails or returns junk) is skipped so it can't
    take down the predictor; ``None`` signals are dropped.
    """
    out: list[Prediction] = []
    for strategy in strategies:
        try:
            prediction = strategy.predict(fw, ctx)
        except Exception:  # noqa: BLE001 - one bad strategy must not stall the pipeline
            continue
        if prediction is not None:
            out.append(prediction)
    return out


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
        # Strategies are sync and some (the LLM-backed ones) make blocking HTTP calls, so
        # run them off the event loop to keep ingestion/features/broadcast responsive.
        predictions = await asyncio.to_thread(predict_all, strategies, fw, ctx)
        for prediction in predictions:
            await bus.send(PREDICTIONS_OUT, fw.symbol, prediction.to_dict())

        processed += 1
        if max_records is not None and processed >= max_records:
            return
