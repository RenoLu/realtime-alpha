import pytest

from realtime_alpha.core import FeatureWindow, PredictionContext, SentimentSnapshot
from realtime_alpha.llm import ModelClient
from realtime_alpha.strategies import registered_ids
from realtime_alpha.strategies.sentiment_llm import SentimentLLMStrategy


class CountingClient(ModelClient):
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls = 0

    def complete(self, *, system, prompt, model=None, max_tokens=1024, thinking=False) -> str:
        self.calls += 1
        return self.text


def _fw(ts: int = 1000, price: float = 100.0) -> FeatureWindow:
    return FeatureWindow(
        "BTCUSDT", ts, price, {"ema_fast": 101.0, "ema_slow": 100.0, "rsi": 60.0, "vol": 0.001}
    )


def _ctx(score: float = 0.4, ts: int = 500) -> PredictionContext:
    return PredictionContext(
        sentiment={"BTCUSDT": SentimentSnapshot("BTCUSDT", score, 10, ts, ("reddit",))}
    )


def test_sentiment_llm_emits_prediction_from_llm_json():
    c = CountingClient('{"yhat": 0.0012, "confidence": 0.7}')
    p = SentimentLLMStrategy(client=c).predict(_fw(), _ctx())
    assert p is not None
    assert p.strategy_id == "sentiment_llm"
    assert p.yhat == pytest.approx(0.0012)
    assert p.confidence == pytest.approx(0.7)
    assert p.ref_price == 100.0 and p.horizon_s == 60


def test_sentiment_llm_returns_none_without_sentiment():
    c = CountingClient('{"yhat":0.01,"confidence":0.5}')
    assert SentimentLLMStrategy(client=c).predict(_fw(), PredictionContext()) is None
    assert SentimentLLMStrategy(client=c).predict(_fw(), None) is None
    assert c.calls == 0  # no LLM call when there's nothing to read


def test_sentiment_llm_memoizes_per_snapshot_and_restamps():
    c = CountingClient('{"yhat":0.002,"confidence":0.6}')
    s = SentimentLLMStrategy(client=c)
    ctx = _ctx()
    s.predict(_fw(ts=1000), ctx)
    p2 = s.predict(_fw(ts=2000), ctx)  # same snapshot + feature bucket, newer window
    assert c.calls == 1  # verdict memoized, not re-queried
    assert p2 is not None
    assert p2.yhat == pytest.approx(0.002)
    assert p2.ts == 2000  # restamped to the current window
    assert p2.ref_price == 100.0


def test_sentiment_llm_clamps_yhat_and_confidence():
    c = CountingClient('{"yhat": 0.9, "confidence": 1.8}')
    p = SentimentLLMStrategy(client=c).predict(_fw(), _ctx())
    assert p is not None
    assert p.yhat == pytest.approx(0.05)  # capped
    assert p.confidence == pytest.approx(1.0)


def test_sentiment_llm_is_registered():
    assert "sentiment_llm" in registered_ids()
