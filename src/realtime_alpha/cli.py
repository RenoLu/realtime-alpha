"""Command-line entry point for running the platform locally.

``realtime-alpha serve`` runs the embedded single-process app (live pipeline +
dashboard). More subcommands (the individual Kafka-topology services) land with the
docker-compose stack.
"""

from __future__ import annotations

import argparse
import os


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="realtime-alpha",
        description="Real-time AI market-prediction platform.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="Run the embedded app (live pipeline + dashboard).")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument(
        "--source",
        choices=["rest", "ws"],
        default=None,
        help="Market-data source (default: REST; WS needs port 9443 reachable).",
    )
    serve.add_argument("--reload", action="store_true", help="Auto-reload on code changes.")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.command == "serve":
        _serve(args)


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
