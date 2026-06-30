"""Command-line entry point for running the platform.

- ``serve`` runs the FastAPI app (embedded pipeline by default; Kafka mode when
  ``RTA_BROKERS`` is set, consuming predictions from the broker).
- ``ingest`` / ``predict`` run those services against a Kafka/Redpanda broker — the
  containers in docker-compose. (The processor runs as a Bytewax flow:
  ``python -m bytewax.run realtime_alpha.processor.bytewax_app:flow``.)
"""

from __future__ import annotations

import argparse
import asyncio
import os


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="realtime-alpha",
        description="Real-time AI market-prediction platform.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="Run the FastAPI app (embedded pipeline + dashboard).")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument(
        "--source",
        choices=["rest", "ws"],
        default=None,
        help="Embedded market-data source (default: REST).",
    )
    serve.add_argument("--reload", action="store_true", help="Auto-reload on code changes.")

    ingest = sub.add_parser("ingest", help="Stream live trades into the broker (Kafka service).")
    ingest.add_argument("--brokers", default="localhost:9092")
    ingest.add_argument("--symbols", default="BTCUSDT,ETHUSDT", help="comma-separated symbols")
    ingest.add_argument("--source", choices=["rest", "ws"], default="rest")

    predict = sub.add_parser("predict", help="Run strategies on features -> predictions (Kafka service).")
    predict.add_argument("--brokers", default="localhost:9092")
    predict.add_argument(
        "--strategies",
        default="momentum",
        help="comma-separated strategy ids (the full LLM lineup runs in embedded `serve`)",
    )

    sentiment = sub.add_parser("sentiment", help="Poll real social sentiment per symbol (standalone).")
    sentiment.add_argument("--symbols", default="BTCUSDT,ETHUSDT", help="comma-separated symbols")
    sentiment.add_argument("--interval", type=float, default=45.0, help="seconds between polls")
    sentiment.add_argument("--once", action="store_true", help="poll one round then exit")

    deep = sub.add_parser("deep", help="Run the off-path deep-analysis chain per symbol (standalone).")
    deep.add_argument("--symbols", default="BTCUSDT,ETHUSDT", help="comma-separated symbols")
    deep.add_argument("--interval", type=float, default=3600.0, help="seconds between runs")
    deep.add_argument("--once", action="store_true", help="run one round then exit")

    evaluate = sub.add_parser(
        "evaluate", help="Score predictions vs realized prices -> scores.out (Kafka service)."
    )
    evaluate.add_argument("--brokers", default="localhost:9092")

    sink = sub.add_parser(
        "sink", help="Persist features/predictions/outcomes to the R2 Parquet lakehouse (Kafka service)."
    )
    sink.add_argument("--brokers", default="localhost:9092")

    backtest = sub.add_parser(
        "backtest", help="Directional accuracy by strategy over the lakehouse history (DuckDB)."
    )
    backtest.add_argument("--root", default=None, help="lakehouse root (default: s3://$RTA_R2_BUCKET)")

    train = sub.add_parser(
        "train", help="Train the ml_model strategy on real klines (walk-forward) -> artifact."
    )
    train.add_argument("--symbols", default="BTCUSDT,ETHUSDT", help="comma-separated symbols")
    train.add_argument("--interval", default="1m")
    train.add_argument("--limit", type=int, default=1000, help="klines per symbol")
    train.add_argument("--horizon", type=int, default=1, help="label horizon in bars")
    train.add_argument("--out", default="models/ml_model.pkl")
    train.add_argument(
        "--register", action="store_true", help="record in model_registry (needs RTA_DATABASE_URL)"
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.command == "serve":
        _serve(args)
    elif args.command == "ingest":
        _ingest(args)
    elif args.command == "predict":
        _predict(args)
    elif args.command == "sentiment":
        _sentiment(args)
    elif args.command == "deep":
        _deep(args)
    elif args.command == "evaluate":
        _evaluate(args)
    elif args.command == "sink":
        _sink(args)
    elif args.command == "backtest":
        _backtest(args)
    elif args.command == "train":
        _train(args)


def _evaluate(args: argparse.Namespace) -> None:
    from .bus.kafka import KafkaBus
    from .evaluation import run_evaluator

    asyncio.run(run_evaluator(KafkaBus(args.brokers, group_id="evaluator")))


def _sink(args: argparse.Namespace) -> None:
    from .bus.kafka import KafkaBus
    from .lakehouse import run_lakehouse_sink, writer_from_env

    writer = writer_from_env()
    if writer is None:
        raise SystemExit(
            "lakehouse sink needs RTA_R2_ENDPOINT / RTA_R2_BUCKET / RTA_R2_ACCESS_KEY_ID / "
            "RTA_R2_SECRET_ACCESS_KEY"
        )
    asyncio.run(run_lakehouse_sink(KafkaBus(args.brokers, group_id="sink"), writer))


def _backtest(args: argparse.Namespace) -> None:
    from .lakehouse import accuracy_by_strategy, connect, r2_config_from_env

    root = args.root or (f"s3://{os.environ['RTA_R2_BUCKET']}" if os.getenv("RTA_R2_BUCKET") else None)
    if root is None:
        raise SystemExit("pass --root <dir|s3://bucket> or set RTA_R2_BUCKET")
    r2 = r2_config_from_env() if root.startswith("s3://") else None
    rows = accuracy_by_strategy(connect(r2=r2), root)
    print(f"{'strategy':16s} {'dir_acc':>8s} {'mae':>9s} {'n':>7s}")
    for r in rows:
        print(f"{r['strategy_id']:16s} {r['dir_acc'] * 100:7.1f}% {r['mae'] * 100:8.3f}% {r['n']:7d}")


def _train(args: argparse.Namespace) -> None:
    from .ml.train import save_artifact, train_model

    symbols = _symbols(args.symbols)
    model, cols, metrics = train_model(
        symbols, interval=args.interval, limit=args.limit, horizon=args.horizon
    )
    save_artifact(model, cols, args.out, model_ver="ml-v1", metrics=metrics)
    acc = metrics["oos_dir_acc"]
    acc_str = f"{acc * 100:.1f}%" if acc is not None else "n/a"
    print(f"trained on {metrics['n']} samples; walk-forward OOS dir-acc {acc_str} (folds {metrics['folds']})")
    print(f"saved -> {args.out}")
    if args.register:
        if not os.getenv("RTA_DATABASE_URL"):
            raise SystemExit("--register needs RTA_DATABASE_URL")
        import time

        from .db import OutcomeStore

        async def _register() -> None:
            store = await OutcomeStore.connect(os.environ["RTA_DATABASE_URL"])
            await store.register_model(
                name="ml_model", version="ml-v1", kind="lightgbm", metrics=metrics,
                artifact_uri=args.out, ts=int(time.time() * 1000),
            )
            await store.close()

        asyncio.run(_register())
        print("registered in model_registry")


def _symbols(arg: str) -> list[str]:
    return [s.strip() for s in arg.split(",") if s.strip()]


def _sentiment(args: argparse.Namespace) -> None:
    from .sentiment import SentimentCache, run_sentiment_poller

    symbols = _symbols(args.symbols)

    async def run() -> None:
        cache = SentimentCache()
        while True:
            await run_sentiment_poller(cache, symbols, interval=0.0, max_rounds=1)
            for sym, snap in cache.snapshot().items():
                src = ",".join(snap.sources) or "none"
                print(f"{sym}: score={snap.score:+.3f} n={snap.n} sources={src}")
            if args.once:
                return
            await asyncio.sleep(args.interval)

    asyncio.run(run())


def _deep(args: argparse.Namespace) -> None:
    from .deep import DeepViewCache, run_deep_analysis
    from .llm import build_model_client
    from .prediction.context import make_deep_context_provider
    from .sentiment import SentimentCache, run_sentiment_poller

    symbols = _symbols(args.symbols)

    async def run() -> None:
        sentiment_cache = SentimentCache()
        await run_sentiment_poller(sentiment_cache, symbols, interval=0.0, max_rounds=1)
        ctx_provider = make_deep_context_provider(sentiment_cache=sentiment_cache)

        def on_view(view) -> None:
            print(
                f"\n=== {view.symbol} [{view.stance}] "
                f"yhat={view.yhat:+.4f} conf={view.confidence:.2f} ===\n{view.briefing_md}\n"
            )

        await run_deep_analysis(
            DeepViewCache(),
            symbols,
            client=build_model_client(),
            context_provider=ctx_provider,
            interval=args.interval,
            max_rounds=1 if args.once else None,
            on_view=on_view,
        )

    asyncio.run(run())


def _serve(args: argparse.Namespace) -> None:
    import uvicorn

    if args.source:
        os.environ["RTA_SOURCE"] = args.source
    # Auto-activate a trained ml_model if its artifact is present and no path was set.
    from pathlib import Path

    if not os.getenv("RTA_MODEL_PATH") and Path("models/ml_model.pkl").exists():
        os.environ["RTA_MODEL_PATH"] = "models/ml_model.pkl"
    uvicorn.run(
        "realtime_alpha.serving.app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


def _ingest(args: argparse.Namespace) -> None:
    from .bus.kafka import KafkaBus
    from .ingestion import binance_rest_trade_stream, binance_trade_stream, run_ingestion

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    source = (
        binance_trade_stream(symbols)
        if args.source == "ws"
        else binance_rest_trade_stream(symbols)
    )
    asyncio.run(run_ingestion(KafkaBus(args.brokers), source))


def _predict(args: argparse.Namespace) -> None:
    from .bus.kafka import KafkaBus
    from .prediction import run_predictor

    strategy_ids = [s.strip() for s in args.strategies.split(",") if s.strip()]
    asyncio.run(run_predictor(KafkaBus(args.brokers, group_id="predictor"), strategy_ids))
