from realtime_alpha.bus import FEATURES_OUT, MemoryBus
from realtime_alpha.core import DeepView, FeatureWindow, Prediction, SentimentSnapshot
from realtime_alpha.deep import DeepContext, DeepViewCache
from realtime_alpha.prediction.context import (
    FeatureCache,
    make_deep_context_provider,
    make_prediction_ctx_provider,
    run_feature_tap,
    summarize_features,
)
from realtime_alpha.prediction.service import predict_all
from realtime_alpha.sentiment import SentimentCache


class _Boom:
    id = "boom"
    horizon_s = 60

    def predict(self, fw, ctx=None):
        raise RuntimeError("kaboom")


class _Emit:
    id = "emit"
    horizon_s = 60

    def predict(self, fw, ctx=None):
        return Prediction("BTCUSDT", 60, 0.01, 0.5, "emit", fw.ts)


def _fw(ts=1, price=100.0):
    return FeatureWindow(
        "BTCUSDT", ts, price, {"ema_fast": 101.0, "ema_slow": 100.0, "rsi": 61.0, "ret_1": 0.004}
    )


def test_predict_all_isolates_a_raising_strategy():
    preds = predict_all([_Boom(), _Emit()], _fw(), None)
    assert [p.strategy_id for p in preds] == ["emit"]  # boom swallowed, emit survives


def test_predict_all_drops_none_signals():
    class _Quiet:
        id = "quiet"
        horizon_s = 60

        def predict(self, fw, ctx=None):
            return None

    assert predict_all([_Quiet()], _fw(), None) == []


def test_make_prediction_ctx_provider_snapshots_caches():
    sc = SentimentCache()
    sc.set(SentimentSnapshot("BTCUSDT", 0.3, 5, 100, ("stocktwits",)))
    dc = DeepViewCache()
    dc.set(DeepView("BTCUSDT", "bullish", 0.01, 0.6, 3600, 100))
    provider = make_prediction_ctx_provider(sentiment_cache=sc, deep_cache=dc)
    ctx = provider()
    assert ctx.sentiment["BTCUSDT"].score == 0.3
    assert ctx.deep["BTCUSDT"].stance == "bullish"


def test_make_prediction_ctx_provider_handles_missing_caches():
    ctx = make_prediction_ctx_provider()()
    assert ctx.sentiment == {} and ctx.deep == {}


def test_summarize_features_is_nonempty_and_readable():
    s = summarize_features(_fw())
    assert "last 100.00" in s
    assert "rsi" in s


def test_make_deep_context_provider_assembles_context():
    fc = FeatureCache()
    fc.set(_fw())
    sc = SentimentCache()
    sc.set(SentimentSnapshot("BTCUSDT", 0.5, 9, 100, ("stocktwits",)))
    provider = make_deep_context_provider(
        feature_cache=fc, sentiment_cache=sc, news_fetch=lambda sym: "headline"
    )
    ctx = provider("BTCUSDT")
    assert isinstance(ctx, DeepContext)
    assert "last 100.00" in ctx.price_summary
    assert ctx.sentiment.score == 0.5
    assert ctx.news == "headline"


def test_make_deep_context_provider_news_fetch_failure_is_swallowed():
    def boom(sym):
        raise RuntimeError("rate limited")

    ctx = make_deep_context_provider(news_fetch=boom)("BTCUSDT")
    assert ctx.news == ""
    assert ctx.price_summary  # falls back to a placeholder, not empty


async def test_run_feature_tap_populates_feature_cache():
    bus = MemoryBus()
    fw = _fw(ts=7, price=123.0)
    await bus.send(FEATURES_OUT, "BTCUSDT", fw.to_dict())
    cache = FeatureCache()
    await run_feature_tap(bus, cache, max_records=1)
    got = cache.get("BTCUSDT")
    assert got is not None and got.ts == 7 and got.last_price == 123.0
