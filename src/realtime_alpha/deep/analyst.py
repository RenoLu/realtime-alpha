"""The off-path analyst chain (lean reimplementation of TradingAgents' multi-agent flow).

Per symbol: three cheap **Haiku** analyst reads (market / sentiment / news), then one
**Opus** bull-vs-bear synthesis (adaptive thinking) that emits a stance + signed
next-hour return + confidence, plus a natural-language briefing. ~4 LLM calls/symbol, so
the hourly scheduler stays well within budget. Prompts are adapted from TradingAgents'
analyst/researcher prompts; the orchestration is ours (no LangGraph).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core import DeepView, SentimentSnapshot
from ..llm import HAIKU, OPUS, ModelClient, extract_json

_YHAT_CAP = 0.10  # the deep horizon is ~1h, so allow a wider band than the 60s strategies


@dataclass(frozen=True, slots=True)
class DeepContext:
    """Everything the analyst chain reads for one symbol (gathered off the hot path)."""

    symbol: str
    price_summary: str = ""
    sentiment: SentimentSnapshot | None = None
    news: str = ""


_MARKET_SYS = (
    "You are a crypto markets analyst. From the price/feature summary, give a concise read "
    "of momentum, trend, and notable risk in 2-3 sentences."
)
_SENTIMENT_SYS = (
    "You are a social-sentiment analyst. Summarize what the crowd positioning implies for "
    "near-term direction in 2-3 sentences. If no data, say so plainly."
)
_NEWS_SYS = (
    "You are a news analyst. Summarize the directional implication of the headlines in 2-3 "
    "sentences. If no news, say so plainly."
)
_SYNTH_SYS = (
    "You are the head of research. Synthesize the market, sentiment, and news analyst notes "
    "into a single bull-vs-bear view for the next hour. Write a short markdown briefing, then "
    "END with a JSON object on its own line: "
    '{"stance": "bullish|bearish|neutral", "yhat": <signed fractional 1h return>, '
    '"confidence": <0..1>}.'
)


def _market_prompt(ctx: DeepContext) -> str:
    return f"Symbol {ctx.symbol}. Price/feature summary: {ctx.price_summary or 'n/a'}."


def _sentiment_prompt(ctx: DeepContext) -> str:
    snap = ctx.sentiment
    if snap is None:
        return f"Symbol {ctx.symbol}. No social-sentiment data available."
    return (
        f"Symbol {ctx.symbol}. Social sentiment score {snap.score:+.2f} over {snap.n} messages "
        f"(sources: {', '.join(snap.sources) or 'none'})."
    )


def _news_prompt(ctx: DeepContext) -> str:
    return f"Symbol {ctx.symbol}. Recent headlines:\n{ctx.news or 'No recent news.'}"


def _synth_prompt(symbol: str, market: str, sentiment: str, news: str) -> str:
    return (
        f"Symbol {symbol}.\n\nMARKET ANALYST:\n{market}\n\nSENTIMENT ANALYST:\n{sentiment}\n\n"
        f"NEWS ANALYST:\n{news}\n\nProduce the briefing and the closing JSON verdict."
    )


def analyze_symbol(
    symbol: str,
    ctx: DeepContext,
    *,
    client: ModelClient,
    ts: int,
    horizon_s: int = 3600,
    quick_model: str = HAIKU,
    deep_model: str = OPUS,
    model_ver: str = "deep-v0",
) -> DeepView:
    market = client.complete(system=_MARKET_SYS, prompt=_market_prompt(ctx), model=quick_model, max_tokens=300)
    sentiment = client.complete(
        system=_SENTIMENT_SYS, prompt=_sentiment_prompt(ctx), model=quick_model, max_tokens=300
    )
    news = client.complete(system=_NEWS_SYS, prompt=_news_prompt(ctx), model=quick_model, max_tokens=300)

    briefing = client.complete(
        system=_SYNTH_SYS,
        prompt=_synth_prompt(symbol, market, sentiment, news),
        model=deep_model,
        max_tokens=900,
        thinking=True,
    )
    data = extract_json(briefing)
    yhat = max(-_YHAT_CAP, min(_YHAT_CAP, float(data.get("yhat", 0.0))))
    confidence = max(0.0, min(1.0, float(data.get("confidence", 0.0))))
    stance = str(data.get("stance", "neutral"))
    return DeepView(
        symbol=symbol,
        stance=stance,
        yhat=yhat,
        confidence=confidence,
        horizon_s=horizon_s,
        ts=ts,
        briefing_md=briefing.strip(),
        model_ver=model_ver,
    )
