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
    predict.add_argument("--strategies", default="momentum", help="comma-separated strategy ids")

    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.command == "serve":
        _serve(args)
    elif args.command == "ingest":
        _ingest(args)
    elif args.command == "predict":
        _predict(args)


def _serve(args: argparse.Namespace) -> None:
    import uvicorn

    if args.source:
        os.environ["RTA_SOURCE"] = args.source
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
