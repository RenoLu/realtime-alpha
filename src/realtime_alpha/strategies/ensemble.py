"""Ensemble: a confidence-weighted blend of other strategies.

Adapts TradingAgents' research-manager *synthesis* idea into a deterministic combiner —
no debate, no LLM. It calls each child strategy on the same window and blends their
signed returns weighted by confidence. Child strategies cache their own expensive work,
so calling one here that also runs standalone is cheap.
"""

from __future__ import annotations

from ..core import FeatureWindow, Prediction, PredictionContext
from .base import Strategy
from .registry import get_strategy, register


@register
class EnsembleStrategy:
    id = "ensemble"

    def __init__(
        self,
        children: list[Strategy] | None = None,
        *,
        child_ids: list[str] | None = None,
        horizon_s: int = 60,
        model_ver: str = "v0",
    ) -> None:
        self.horizon_s = horizon_s
        self._children = children  # explicit instances (tests / custom wiring)
        self._child_ids = child_ids or ["momentum", "sentiment_llm"]
        self._model_ver = model_ver

    def _resolve(self) -> list[Strategy]:
        # Lazy so constructing the ensemble doesn't force-instantiate children at import.
        if self._children is None:
            self._children = [get_strategy(cid) for cid in self._child_ids]
        return self._children

    def predict(
        self, fw: FeatureWindow, ctx: PredictionContext | None = None
    ) -> Prediction | None:
        preds = [p for c in self._resolve() if (p := c.predict(fw, ctx)) is not None]
        total_w = sum(p.confidence for p in preds)
        if not preds or total_w <= 0:
            return None

        yhat = sum(p.yhat * p.confidence for p in preds) / total_w
        confidence = min(1.0, total_w / len(preds))
        return Prediction(
            symbol=fw.symbol,
            horizon_s=self.horizon_s,
            yhat=yhat,
            confidence=confidence,
            strategy_id=self.id,
            ts=fw.ts,
            model_ver=self._model_ver,
            ref_price=fw.last_price,
        )
