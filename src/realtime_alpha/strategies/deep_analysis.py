"""deep_analysis: serves the off-path deep view as a (slow-horizon) prediction.

The expensive multi-agent analysis runs on a schedule (see ``deep/scheduler.py``) and
writes a standing ``DeepView`` per symbol into the cache; this strategy just reads it from
``ctx.deep`` and re-emits it (restamped to the current window) so the live leaderboard can
grade the deep signal alongside the fast strategies. No LLM call on the hot path.
"""

from __future__ import annotations

from ..core import FeatureWindow, Prediction, PredictionContext
from .registry import register


@register
class DeepAnalysisStrategy:
    id = "deep_analysis"

    def __init__(self, *, horizon_s: int = 3600, model_ver: str = "v0") -> None:
        self.horizon_s = horizon_s
        self._model_ver = model_ver

    def predict(
        self, fw: FeatureWindow, ctx: PredictionContext | None = None
    ) -> Prediction | None:
        view = ctx.deep.get(fw.symbol) if ctx else None
        if view is None:
            return None
        return Prediction(
            symbol=fw.symbol,
            horizon_s=view.horizon_s,
            yhat=view.yhat,
            confidence=view.confidence,
            strategy_id=self.id,
            ts=fw.ts,
            model_ver=view.model_ver,
            ref_price=fw.last_price,
        )
