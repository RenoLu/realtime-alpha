"""sentiment_llm: a compact LLM read of features + social sentiment.

Adapts TradingAgents' Sentiment/Market analyst into a single cheap LLM call per symbol:
it reads the streaming features plus the cached social-sentiment snapshot (from ``ctx``)
and returns a signed next-horizon return + confidence. The verdict is **memoized** per
(symbol, sentiment timestamp, coarse feature bucket) and re-emitted (restamped) on every
window between refreshes, so cost stays bounded on the hot path.
"""

from __future__ import annotations

from ..core import FeatureWindow, Prediction, PredictionContext, SentimentSnapshot
from ..llm import HAIKU, ModelClient, build_model_client, extract_json
from .registry import register

_SYSTEM = (
    "You are a crypto market microstructure analyst. From a short-horizon technical and "
    "social-sentiment snapshot, forecast the very-near-term return. Be calibrated -- small "
    "moves are normal and confidence should reflect genuine conviction."
)

_YHAT_CAP = 0.05  # clamp the LLM's signed-return forecast to a sane band


@register
class SentimentLLMStrategy:
    id = "sentiment_llm"

    def __init__(
        self,
        client: ModelClient | None = None,
        *,
        horizon_s: int = 60,
        model: str = HAIKU,
        model_ver: str = "v0",
    ) -> None:
        self.horizon_s = horizon_s
        self._client = client or build_model_client(model=model)
        self._model = model
        self._model_ver = model_ver
        self._memo: dict[str, tuple[tuple, Prediction]] = {}  # symbol -> (key, verdict)

    def predict(
        self, fw: FeatureWindow, ctx: PredictionContext | None = None
    ) -> Prediction | None:
        snap = ctx.sentiment.get(fw.symbol) if ctx else None
        if snap is None:
            return None  # this is the *sentiment* strategy; no snapshot -> no signal

        key = self._memo_key(fw, snap)
        cached = self._memo.get(fw.symbol)
        if cached is not None and cached[0] == key:
            return self._restamp(cached[1], fw)

        yhat, confidence = self._ask(fw, snap)
        verdict = Prediction(
            symbol=fw.symbol,
            horizon_s=self.horizon_s,
            yhat=yhat,
            confidence=confidence,
            strategy_id=self.id,
            ts=fw.ts,
            model_ver=self._model_ver,
            ref_price=fw.last_price,
        )
        self._memo[fw.symbol] = (key, verdict)
        return verdict

    def _ask(self, fw: FeatureWindow, snap: SentimentSnapshot) -> tuple[float, float]:
        prompt = (
            f"Symbol {fw.symbol}. Social sentiment {snap.score:+.2f} "
            f"(n={snap.n}, sources={','.join(snap.sources) or 'none'}). "
            f"RSI {fw.features.get('rsi', 50.0):.0f}, EMA spread {self._ema_spread(fw):+.4f}, "
            f"vol {fw.features.get('vol', 0.0):.5f}. "
            f"Forecast the next-{self.horizon_s}s fractional return. "
            'Respond ONLY as JSON: {"yhat": <signed float>, "confidence": <0..1>}.'
        )
        data = extract_json(
            self._client.complete(system=_SYSTEM, prompt=prompt, model=self._model, max_tokens=200)
        )
        yhat = max(-_YHAT_CAP, min(_YHAT_CAP, float(data["yhat"])))
        confidence = max(0.0, min(1.0, float(data["confidence"])))
        return yhat, confidence

    @staticmethod
    def _ema_spread(fw: FeatureWindow) -> float:
        fast, slow = fw.features.get("ema_fast"), fw.features.get("ema_slow")
        if fast is None or not slow:
            return 0.0
        return (fast - slow) / slow

    def _memo_key(self, fw: FeatureWindow, snap: SentimentSnapshot) -> tuple:
        # Coarse buckets so feature jitter doesn't re-trigger the LLM; new snapshot does.
        rsi_bucket = round(fw.features.get("rsi", 50.0) / 5.0)
        spread_bucket = round(self._ema_spread(fw) * 1000)
        return (snap.ts, round(snap.score, 1), rsi_bucket, spread_bucket)

    def _restamp(self, verdict: Prediction, fw: FeatureWindow) -> Prediction:
        return Prediction(
            symbol=fw.symbol,
            horizon_s=verdict.horizon_s,
            yhat=verdict.yhat,
            confidence=verdict.confidence,
            strategy_id=verdict.strategy_id,
            ts=fw.ts,
            model_ver=verdict.model_ver,
            ref_price=fw.last_price,
        )
