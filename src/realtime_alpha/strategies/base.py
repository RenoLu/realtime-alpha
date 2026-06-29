"""The Strategy contract.

A strategy turns one ``FeatureWindow`` into a ``Prediction`` (or ``None`` when it has
no signal). It is intentionally tiny so new approaches — classical ML, a deep forecaster,
an LLM sentiment signal, an ensemble — drop in without touching the pipeline. The
prediction service runs every enabled strategy per feature window and tags each output
with ``strategy_id`` so the evaluator can score them independently.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..core import FeatureWindow, Prediction, PredictionContext


@runtime_checkable
class Strategy(Protocol):
    id: str
    horizon_s: int

    def predict(
        self, fw: FeatureWindow, ctx: PredictionContext | None = None
    ) -> Prediction | None:
        """Return a prediction for ``fw``, or ``None`` if the strategy has no signal.

        ``ctx`` carries shared slow-moving signals (sentiment, deep views); strategies
        that don't need them ignore it.
        """
        ...
