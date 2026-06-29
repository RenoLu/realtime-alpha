"""The outcome evaluator: a time-based join of predictions against realized prices.

Each prediction is held *pending* until a feature window arrives whose timestamp has
passed the prediction's ``target_ts`` (``pred.ts + horizon_s*1000``); that window's
``last_price`` is the realized price, and the prediction is scored and emitted to
``scores.out``. The join state lives in ``OutcomeJoiner`` (pure, fully unit-tested);
``run_evaluator`` wires it to the bus with one consumer per input topic.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict

from ..bus import FEATURES_OUT, PREDICTIONS_OUT, SCORES_OUT, Bus
from ..core import FeatureWindow, Outcome, Prediction
from .metrics import score_prediction


class OutcomeJoiner:
    """Holds pending predictions and scores them once their horizon has elapsed."""

    def __init__(self) -> None:
        self._pending: dict[str, list[Prediction]] = defaultdict(list)

    def add_prediction(self, pred: Prediction) -> None:
        self._pending[pred.symbol].append(pred)

    def observe_price(self, symbol: str, price: float, ts: int) -> list[Outcome]:
        """Score (and drop) every pending prediction for ``symbol`` matured by ``ts``."""
        pending = self._pending.get(symbol)
        if not pending:
            return []
        matured = [p for p in pending if p.target_ts <= ts]
        if not matured:
            return []
        self._pending[symbol] = [p for p in pending if p.target_ts > ts]
        return [score_prediction(p, price, ts) for p in matured]

    @property
    def pending_count(self) -> int:
        return sum(len(v) for v in self._pending.values())


async def run_evaluator(
    bus: Bus,
    *,
    joiner: OutcomeJoiner | None = None,
    max_scores: int | None = None,
) -> None:
    joiner = joiner or OutcomeJoiner()
    scored = 0
    done = asyncio.Event()

    async def consume_predictions() -> None:
        async for rec in bus.stream(PREDICTIONS_OUT):
            joiner.add_prediction(Prediction.from_dict(rec.value))
            if done.is_set():
                return

    async def consume_features() -> None:
        nonlocal scored
        async for rec in bus.stream(FEATURES_OUT):
            fw = FeatureWindow.from_dict(rec.value)
            for outcome in joiner.observe_price(fw.symbol, fw.last_price, fw.ts):
                await bus.send(SCORES_OUT, outcome.symbol, outcome.to_dict())
                scored += 1
                if max_scores is not None and scored >= max_scores:
                    done.set()
                    return

    # The predictions consumer is created first so its pre-filled records are drained
    # before any feature window is processed (a prediction is always added before the
    # window that matures it, which in real time arrives `horizon` seconds later).
    pred_task = asyncio.create_task(consume_predictions())
    feat_task = asyncio.create_task(consume_features())
    try:
        if max_scores is not None:
            await feat_task
        else:
            await asyncio.gather(pred_task, feat_task)
    finally:
        pred_task.cancel()
        feat_task.cancel()
