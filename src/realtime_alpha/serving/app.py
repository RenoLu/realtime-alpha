"""FastAPI app + embedded single-process pipeline.

In embedded mode the app runs the whole pipeline in-process over the in-memory bus —
live Binance data → features → predictions → WebSocket fan-out — so the dashboard works
with real data and no broker. (The Bytewax + Kafka topology is the scale-out path.)

``create_app(start_pipeline=False)`` builds the app without the background tasks, for
route tests.
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from ..bus import MemoryBus
from ..core import DeepView
from ..deep import DeepViewCache, run_deep_analysis
from ..evaluation import Leaderboard, run_evaluator
from ..ingestion import binance_rest_trade_stream, binance_trade_stream, run_ingestion
from ..llm import build_model_client
from ..prediction import run_predictor
from ..prediction.context import (
    FeatureCache,
    make_deep_context_provider,
    make_prediction_ctx_provider,
    run_feature_tap,
)
from ..processor import run_feature_processor
from ..sentiment import SentimentCache, run_sentiment_poller
from .broadcaster import broadcast_predictions
from .leaderboard_feed import leaderboard_msg, run_leaderboard_feed
from .ws_hub import ConnectionManager


def _briefing_msg(view: DeepView) -> dict[str, Any]:
    return {
        "type": "briefing",
        "symbol": view.symbol,
        "stance": view.stance,
        "yhat": view.yhat,
        "confidence": view.confidence,
        "briefing_md": view.briefing_md,
        "ts": view.ts,
    }


DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT"]
# momentum (zero-cost baseline) + the TradingAgents-derived strategies. The LLM-backed
# ones (sentiment_llm, ensemble, deep_analysis) light up when ANTHROPIC_API_KEY is set;
# key-less they emit zero-confidence predictions (via the deterministic mock client).
DEFAULT_STRATEGIES = ["momentum", "sentiment_llm", "ensemble", "deep_analysis", "ml_model"]
DEFAULT_FEATURE_CFG = {"ema_fast": 12, "ema_slow": 26, "rsi_period": 14, "vol_window": 20}


def _source_factory(symbols: list[str]) -> AsyncIterator[dict[str, Any]]:
    """Pick the market-data source. Real data either way; REST is the default because the
    WS port (:9443) is blocked on some networks."""
    if os.getenv("RTA_SOURCE", "rest").lower() == "ws":
        return binance_trade_stream(symbols)
    return binance_rest_trade_stream(symbols)


def _make_news_fetch() -> Any:
    """Best-effort recent-news fetch per symbol (vendored Google/yfinance connector).

    Returns "" on any failure (missing deps, rate limit, no yahoo mapping) so the deep
    analyst degrades gracefully rather than blocking.
    """
    from datetime import datetime, timedelta

    from ..sentiment.crypto_symbols import connectors_for

    def fetch(symbol: str) -> str:
        conn = connectors_for(symbol)
        if not conn or "yahoo" not in conn:
            return ""
        from ..dataflows.yfinance_news import get_news_yfinance

        end = datetime.now(UTC).date()
        start = end - timedelta(days=2)
        return get_news_yfinance(conn["yahoo"], start.isoformat(), end.isoformat())

    return fetch


def _build_lakehouse_writer() -> Any:
    """An R2 Parquet writer if R2 creds are set, else None (lakehouse archive disabled)."""
    if not os.getenv("RTA_R2_BUCKET"):
        return None  # cheap gate so we don't import the lakehouse extra when it's off
    from ..lakehouse import writer_from_env

    return writer_from_env()


async def _maybe_store() -> Any:
    """An initialized OutcomeStore if RTA_DATABASE_URL is set, else None.

    Resilient: a missing asyncpg or an unreachable DB degrades to in-memory rather than
    taking down the app, so a DB outage never breaks the live demo.
    """
    dsn = os.getenv("RTA_DATABASE_URL")
    if not dsn:
        return None
    try:
        from ..db import OutcomeStore

        return await OutcomeStore.connect(dsn)
    except Exception:  # noqa: BLE001 - persistence is best-effort
        return None


def _frontend_dist() -> Path | None:
    """The built React dashboard, if present (else the app serves the inline page)."""
    override = os.getenv("RTA_FRONTEND_DIST")
    candidates = [Path(override)] if override else []
    candidates.append(Path(__file__).resolve().parents[3] / "frontend" / "dist")
    for c in candidates:
        if c.is_dir() and (c / "index.html").exists():
            return c
    return None


def create_app(
    *,
    symbols: list[str] | None = None,
    strategy_ids: list[str] | None = None,
    feature_cfg: dict[str, Any] | None = None,
    cors_origins: list[str] | None = None,
    start_pipeline: bool = True,
) -> FastAPI:
    symbols = symbols or DEFAULT_SYMBOLS
    strategy_ids = strategy_ids or DEFAULT_STRATEGIES
    feature_cfg = feature_cfg or DEFAULT_FEATURE_CFG
    cors_origins = cors_origins or ["http://localhost:5173", "http://localhost:8000"]

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.manager = ConnectionManager()
        app.state.tasks = []
        app.state.bus = None
        app.state.store = None
        brokers = os.getenv("RTA_BROKERS")
        if start_pipeline and brokers:
            # Kafka mode: ingestion/processor/predictor are separate services; serving
            # just consumes predictions.out from the broker and fans them out.
            from ..bus.kafka import KafkaBus

            bus = KafkaBus(brokers)
            app.state.bus = bus
            leaderboard = Leaderboard()
            store = await _maybe_store()
            if store is not None:
                leaderboard.seed(await store.recent_outcomes())  # durable rebuild on restart
            app.state.store = store
            app.state.leaderboard = leaderboard
            # The lakehouse sink runs as its own `sink` service in this topology.
            app.state.tasks = [
                asyncio.create_task(broadcast_predictions(bus, app.state.manager)),
                asyncio.create_task(
                    run_leaderboard_feed(bus, app.state.manager, leaderboard, store=store)
                ),
            ]
        elif start_pipeline:
            # Embedded mode: run the whole pipeline in-process over the in-memory bus,
            # including the sentiment poller + off-path deep-analysis scheduler that feed
            # the LLM strategies their PredictionContext.
            bus = MemoryBus()
            app.state.bus = bus
            sentiment_cache = SentimentCache()
            deep_cache = DeepViewCache()
            feature_cache = FeatureCache()
            model_client = build_model_client()
            ctx_provider = make_prediction_ctx_provider(
                sentiment_cache=sentiment_cache, deep_cache=deep_cache
            )
            # News is opt-in (RTA_ENABLE_NEWS=1): the vendored yfinance connector spawns
            # internal worker threads that starve the event loop under our concurrency, and
            # its crypto coverage is thin. The deep analyst degrades cleanly without it
            # (market + sentiment). Inject a reliable news source here when available.
            news_fetch = _make_news_fetch() if os.getenv("RTA_ENABLE_NEWS") else None
            deep_ctx_provider = make_deep_context_provider(
                feature_cache=feature_cache,
                sentiment_cache=sentiment_cache,
                news_fetch=news_fetch,
            )
            sentiment_interval = float(os.getenv("RTA_SENTIMENT_INTERVAL", "45"))
            deep_interval = float(os.getenv("RTA_DEEP_INTERVAL", "3600"))
            manager = app.state.manager
            leaderboard = Leaderboard()
            store = await _maybe_store()
            if store is not None:
                leaderboard.seed(await store.recent_outcomes())  # durable rebuild on restart
            app.state.store = store
            lakehouse_writer = _build_lakehouse_writer()
            app.state.deep_cache = deep_cache  # so a new WS connection can replay briefings
            app.state.leaderboard = leaderboard  # ditto for the standings + /api/leaderboard
            briefing_tasks: set[asyncio.Task] = set()
            app.state.briefing_tasks = briefing_tasks

            def on_view(view: DeepView) -> None:
                task = asyncio.create_task(manager.broadcast(_briefing_msg(view)))
                briefing_tasks.add(task)
                task.add_done_callback(briefing_tasks.discard)

            app.state.tasks = [
                asyncio.create_task(run_ingestion(bus, _source_factory(symbols))),
                asyncio.create_task(run_feature_processor(bus, **feature_cfg)),
                asyncio.create_task(run_feature_tap(bus, feature_cache)),
                asyncio.create_task(
                    run_sentiment_poller(sentiment_cache, symbols, interval=sentiment_interval)
                ),
                asyncio.create_task(
                    run_deep_analysis(
                        deep_cache,
                        symbols,
                        client=model_client,
                        context_provider=deep_ctx_provider,
                        interval=deep_interval,
                        on_view=on_view,
                    )
                ),
                asyncio.create_task(run_predictor(bus, strategy_ids, ctx_provider=ctx_provider)),
                asyncio.create_task(broadcast_predictions(bus, app.state.manager)),
                asyncio.create_task(run_evaluator(bus)),
                asyncio.create_task(
                    run_leaderboard_feed(bus, manager, leaderboard, store=store)
                ),
            ]
            if lakehouse_writer is not None:
                from ..lakehouse import run_lakehouse_sink

                app.state.tasks.append(
                    asyncio.create_task(run_lakehouse_sink(bus, lakehouse_writer))
                )
        try:
            yield
        finally:
            for task in app.state.tasks:
                task.cancel()
            if app.state.store is not None:
                await app.state.store.close()
            if app.state.bus is not None and hasattr(app.state.bus, "close"):
                await app.state.bus.close()

    app = FastAPI(title="realtime-alpha", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/symbols")
    async def get_symbols() -> dict[str, list[str]]:
        return {"symbols": symbols, "strategies": strategy_ids}

    @app.get("/api/leaderboard")
    async def get_leaderboard() -> dict[str, list[dict[str, Any]]]:
        lb = getattr(app.state, "leaderboard", None)
        standings = lb.standings() if lb is not None else []
        return {"standings": [s.to_dict() for s in standings]}

    @app.websocket("/ws")
    async def ws(websocket: WebSocket) -> None:
        await websocket.accept()
        manager: ConnectionManager = websocket.app.state.manager
        manager.connect(websocket)
        # Replay the standing deep-analysis briefings so a dashboard opened between hourly
        # runs sees them immediately instead of waiting for the next refresh.
        deep_cache = getattr(websocket.app.state, "deep_cache", None)
        if deep_cache is not None:
            for view in deep_cache.snapshot().values():
                await websocket.send_text(json.dumps(_briefing_msg(view)))
        leaderboard = getattr(websocket.app.state, "leaderboard", None)
        if leaderboard is not None and (standings := leaderboard.standings()):
            await websocket.send_text(json.dumps(leaderboard_msg(standings)))
        try:
            while True:
                await websocket.receive_text()  # ignore client input; wait for disconnect
        except WebSocketDisconnect:
            pass
        finally:
            manager.disconnect(websocket)

    # Serve the built React dashboard if present; otherwise the zero-build page.
    # The API/WS routes above are registered first, so they take precedence over the mount.
    dist = _frontend_dist()
    if dist is not None:
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="frontend")
    else:

        @app.get("/", response_class=HTMLResponse)
        async def index() -> str:
            return _INDEX_HTML

    return app


# A zero-build live view so the embedded app is immediately demoable; the React
# dashboard (frontend/) is the richer version.
_INDEX_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>realtime-alpha</title>
<style>
 body{font:14px system-ui;margin:2rem;background:#0b0e14;color:#e6e6e6}
 h1{font-size:1.1rem} table{border-collapse:collapse;margin-top:1rem}
 td,th{border:1px solid #2a2f3a;padding:.4rem .8rem;text-align:right}
 th{color:#8a93a6;font-weight:600} .up{color:#3fb950} .down{color:#f85149}
 #status{color:#8a93a6}
</style></head><body>
<h1>realtime-alpha &mdash; live predictions</h1>
<div id="status">connecting&hellip;</div>
<table><thead><tr><th>symbol</th><th>strategy</th><th>dir</th><th>yhat</th><th>conf</th></tr></thead>
<tbody id="rows"></tbody></table>
<script>
 const rows = {}, tbody = document.getElementById('rows'), status = document.getElementById('status');
 const ws = new WebSocket((location.protocol==='https:'?'wss':'ws')+'://'+location.host+'/ws');
 ws.onopen = () => status.textContent = 'connected';
 ws.onclose = () => status.textContent = 'disconnected';
 ws.onmessage = (e) => {
   const m = JSON.parse(e.data); if (m.type !== 'prediction') return;
   const k = m.symbol + '|' + m.strategy_id;
   let tr = rows[k]; if (!tr){ tr = rows[k] = tbody.insertRow(); for(let i=0;i<5;i++) tr.insertCell(); }
   const dir = m.yhat>0?'up':(m.yhat<0?'down':'');
   tr.cells[0].textContent=m.symbol; tr.cells[1].textContent=m.strategy_id;
   tr.cells[2].textContent=dir||'flat'; tr.cells[2].className=dir;
   tr.cells[3].textContent=(+m.yhat).toFixed(6); tr.cells[4].textContent=(+m.confidence).toFixed(2);
 };
</script></body></html>"""
