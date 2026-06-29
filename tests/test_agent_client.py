import json

from realtime_alpha.core import FeatureWindow, PredictionContext, SentimentSnapshot
from realtime_alpha.deep import DeepContext, analyze_symbol
from realtime_alpha.llm import AgentClient, build_model_client, extract_json
from realtime_alpha.strategies.sentiment_llm import SentimentLLMStrategy

# system prompts only need to contain the routing keywords the AgentClient matches on
SENTIMENT_SYS = "You are a crypto market microstructure analyst. Forecast the return."
SYNTH_SYS = "You are the head of research. Synthesize the bull and bear cases."
READ_SYS = "You are a crypto markets analyst. Read the price summary."


def _write(path, signals: dict) -> str:
    p = path / "agent_signals.json"
    p.write_text(json.dumps({"signals": signals}), encoding="utf-8")
    return str(p)


def test_serves_authored_sentiment_verdict(tmp_path):
    path = _write(tmp_path, {"BTCUSDT": {"sentiment": {"yhat": 0.0012, "confidence": 0.6}}})
    out = AgentClient(path).complete(system=SENTIMENT_SYS, prompt="Symbol BTCUSDT. RSI 60.")
    assert extract_json(out) == {"yhat": 0.0012, "confidence": 0.6}


def test_serves_authored_deep_briefing_and_verdict(tmp_path):
    path = _write(
        tmp_path,
        {"BTCUSDT": {"deep": {"stance": "bullish", "yhat": 0.005, "confidence": 0.62,
                              "briefing_md": "## BTC is strong"}}},
    )
    out = AgentClient(path).complete(system=SYNTH_SYS, prompt="Symbol BTCUSDT. notes...")
    assert "## BTC is strong" in out
    assert extract_json(out) == {"stance": "bullish", "yhat": 0.005, "confidence": 0.62}


def test_neutral_fallback_when_symbol_missing(tmp_path):
    path = _write(tmp_path, {"BTCUSDT": {"sentiment": {"yhat": 0.01, "confidence": 0.7}}})
    out = AgentClient(path).complete(system=SENTIMENT_SYS, prompt="Symbol ETHUSDT. RSI 40.")
    assert extract_json(out)["confidence"] == 0.0  # unknown symbol -> inert


def test_deep_analyst_reads_get_a_stub(tmp_path):
    path = _write(tmp_path, {})
    out = AgentClient(path).complete(system=READ_SYS, prompt="Symbol BTCUSDT. price up.")
    assert isinstance(out, str) and out  # non-empty stub; the authored synthesis is what matters


def test_rereads_file_each_call_for_live_refresh(tmp_path):
    path = _write(tmp_path, {"BTCUSDT": {"sentiment": {"yhat": 0.001, "confidence": 0.5}}})
    client = AgentClient(path)
    assert extract_json(client.complete(system=SENTIMENT_SYS, prompt="Symbol BTCUSDT."))["yhat"] == 0.001
    _write(tmp_path, {"BTCUSDT": {"sentiment": {"yhat": -0.002, "confidence": 0.8}}})
    assert extract_json(client.complete(system=SENTIMENT_SYS, prompt="Symbol BTCUSDT."))["yhat"] == -0.002


def test_build_model_client_agent_mode(tmp_path, monkeypatch):
    path = _write(tmp_path, {})
    monkeypatch.setenv("RTA_MODEL", "agent")
    monkeypatch.setenv("RTA_AGENT_SIGNALS", path)
    assert isinstance(build_model_client(), AgentClient)


# --- the payoff: both strategies serve authored analysis, unchanged ------------------

def test_sentiment_llm_serves_authored_signal(tmp_path):
    path = _write(tmp_path, {"BTCUSDT": {"sentiment": {"yhat": 0.0009, "confidence": 0.58}}})
    fw = FeatureWindow("BTCUSDT", 1000, 100.0, {"ema_fast": 101.0, "ema_slow": 100.0, "rsi": 60.0})
    ctx = PredictionContext(sentiment={"BTCUSDT": SentimentSnapshot("BTCUSDT", 0.4, 9, 500, ("stocktwits",))})
    p = SentimentLLMStrategy(client=AgentClient(path)).predict(fw, ctx)
    assert p is not None
    assert p.yhat == 0.0009 and p.confidence == 0.58


def test_deep_analysis_serves_authored_view(tmp_path):
    path = _write(
        tmp_path,
        {"ETHUSDT": {"deep": {"stance": "bearish", "yhat": -0.008, "confidence": 0.55,
                              "briefing_md": "## ETH faces resistance"}}},
    )
    view = analyze_symbol("ETHUSDT", DeepContext("ETHUSDT", price_summary="flat"),
                          client=AgentClient(path), ts=1700)
    assert view.stance == "bearish" and view.yhat == -0.008 and view.confidence == 0.55
    assert "ETH faces resistance" in view.briefing_md
