import pytest

from realtime_alpha.core import SentimentSnapshot
from realtime_alpha.deep import DeepContext, DeepViewCache, analyze_symbol, run_deep_analysis
from realtime_alpha.llm import MockClient


def _ctx(symbol: str = "BTCUSDT") -> DeepContext:
    return DeepContext(
        symbol=symbol,
        price_summary="last 100.0, ret_1 +0.4%, rsi 61",
        sentiment=SentimentSnapshot(symbol, 0.5, 20, 100, ("stocktwits",)),
        news="BTC ETF inflows continue",
    )


def _responder_factory(calls: list[str], synth_json: str):
    def responder(system: str, prompt: str) -> str:
        calls.append(system)
        if "synthesi" in system.lower():
            return f"## {{}} deep view\nBulls argue X. Bears argue Y.\n\n{synth_json}"
        return "analyst read: mildly constructive"

    return responder


def test_analyze_symbol_runs_bounded_chain_and_parses_verdict():
    calls: list[str] = []
    client = MockClient(
        responder=_responder_factory(calls, '{"stance": "bullish", "yhat": 0.015, "confidence": 0.62}')
    )
    view = analyze_symbol("BTCUSDT", _ctx(), client=client, ts=1700, horizon_s=3600)

    assert view.symbol == "BTCUSDT"
    assert view.stance == "bullish"
    assert view.yhat == pytest.approx(0.015)
    assert view.confidence == pytest.approx(0.62)
    assert view.horizon_s == 3600 and view.ts == 1700
    assert "deep view" in view.briefing_md
    assert len(calls) == 4  # 3 quick analyst reads + 1 deep synthesis -> bounded cost


def test_analyze_symbol_clamps_and_defaults_stance():
    calls: list[str] = []
    client = MockClient(responder=_responder_factory(calls, '{"yhat": 0.9, "confidence": 1.8}'))
    view = analyze_symbol("BTCUSDT", _ctx(), client=client, ts=1)
    assert view.yhat == pytest.approx(0.10)  # capped at the deep band
    assert view.confidence == pytest.approx(1.0)
    assert view.stance == "neutral"  # default when synthesis omits it


async def test_run_deep_analysis_populates_cache_and_broadcasts():
    cache = DeepViewCache()
    seen = []
    client = MockClient(
        responder=lambda s, p: (
            '{"stance":"bearish","yhat":-0.01,"confidence":0.4}' if "synthesi" in s.lower() else "read"
        )
    )
    await run_deep_analysis(
        cache,
        ["BTCUSDT"],
        client=client,
        context_provider=lambda sym: DeepContext(sym, price_summary="flat"),
        now_ms=lambda: 1700,
        interval=0.0,
        max_rounds=1,
        on_view=seen.append,
    )
    v = cache.get("BTCUSDT")
    assert v is not None
    assert v.stance == "bearish" and v.yhat == pytest.approx(-0.01)
    assert v.ts == 1700
    assert len(seen) == 1 and seen[0] is v
