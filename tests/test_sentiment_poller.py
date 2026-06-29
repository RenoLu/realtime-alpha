import pytest

from realtime_alpha.core import SentimentSnapshot
from realtime_alpha.sentiment import (
    SentimentCache,
    aggregate_sentiment,
    connectors_for,
    run_sentiment_poller,
)


def test_aggregate_scores_from_stocktwits_bull_bear():
    snap = aggregate_sentiment(
        "BTCUSDT", stocktwits_summary="Bullish: 7 (70%) · Bearish: 3 (30%)", ts=1700
    )
    assert snap.symbol == "BTCUSDT"
    assert snap.score == pytest.approx(0.4)  # (7-3)/10
    assert snap.n == 10
    assert snap.sources == ("stocktwits",)


def test_aggregate_negative_when_bearish_dominates():
    snap = aggregate_sentiment("BTCUSDT", stocktwits_summary="Bullish: 1 · Bearish: 4", ts=1)
    assert snap.score == pytest.approx(-0.6)  # (1-4)/5


def test_aggregate_marks_reddit_source_and_is_neutral_without_scored_data():
    snap = aggregate_sentiment("BTCUSDT", reddit_text="some posts", ts=1)
    assert snap.score == 0.0 and snap.n == 0
    assert snap.sources == ("reddit",)


def test_aggregate_empty_is_neutral_no_sources():
    snap = aggregate_sentiment("BTCUSDT", ts=1)
    assert isinstance(snap, SentimentSnapshot)
    assert snap.score == 0.0 and snap.n == 0 and snap.sources == ()


def test_sentiment_cache_set_get_snapshot():
    c = SentimentCache()
    assert c.get("BTCUSDT") is None
    s = SentimentSnapshot("BTCUSDT", 0.2, 5, 1700, ("stocktwits",))
    c.set(s)
    assert c.get("BTCUSDT") is s
    assert c.snapshot() == {"BTCUSDT": s}


def test_connectors_for_maps_known_symbols():
    assert connectors_for("BTCUSDT")["stocktwits"] == "BTC.X"
    assert connectors_for("DOGEUSDT") is None  # unmapped


async def test_poller_populates_cache_from_injected_fetchers():
    cache = SentimentCache()
    await run_sentiment_poller(
        cache,
        ["BTCUSDT"],
        stocktwits_fetch=lambda t: "Bullish: 8 (80%) · Bearish: 2 (20%)",
        reddit_fetch=lambda t: "reddit posts",
        now_ms=lambda: 1700,
        interval=0.0,
        max_rounds=1,
    )
    snap = cache.get("BTCUSDT")
    assert snap is not None
    assert snap.score == pytest.approx(0.6)
    assert snap.n == 10
    assert set(snap.sources) == {"stocktwits", "reddit"}
    assert snap.ts == 1700
