"""Momentum: a training-free baseline and control.

Signal is the relative spread between a fast and slow EMA. When the fast EMA leads
the slow one the recent trend is up, so the next-horizon return is predicted positive
(and vice versa). It needs no model, which makes it the natural M1 vertical-slice
strategy and a permanent baseline the leaderboard measures everything else against.
"""

from __future__ import annotations

from ..core import FeatureWindow, Prediction, PredictionContext
from .registry import register


@register
class MomentumStrategy:
    id = "momentum"

    def __init__(
        self,
        horizon_s: int = 60,
        *,
        scale: float = 20.0,
        min_confidence: float = 0.05,
        model_ver: str = "v0",
    ) -> None:
        self.horizon_s = horizon_s
        self._scale = scale
        self._min_confidence = min_confidence
        self._model_ver = model_ver

    def predict(
        self, fw: FeatureWindow, ctx: PredictionContext | None = None
    ) -> Prediction | None:
        ema_fast = fw.features.get("ema_fast")
        ema_slow = fw.features.get("ema_slow")
        if ema_fast is None or ema_slow is None or ema_slow == 0:
            return None

        spread = (ema_fast - ema_slow) / ema_slow
        confidence = max(self._min_confidence, min(1.0, abs(spread) * self._scale))
        return Prediction(
            symbol=fw.symbol,
            horizon_s=self.horizon_s,
            yhat=spread,
            confidence=confidence,
            strategy_id=self.id,
            ts=fw.ts,
            model_ver=self._model_ver,
            ref_price=fw.last_price,
        )
