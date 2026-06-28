# realtime-alpha

**A real-time AI market-prediction platform.** It ingests live crypto market data over
exchange WebSockets, computes streaming features, runs **pluggable prediction strategies**
that forecast the next-horizon move, and — the part most demos skip — **continuously grades
its own predictions against what actually happened**, so the dashboard shows a live
leaderboard of which strategy is most accurate *right now*, on real data.

> Status: in active development. Built end-to-end from real-time ingestion through online
> evaluation and deployment (AWS via Terraform; an always-on Fly.io demo mirror).

## Architecture

```
 Real market data (Binance.US / Coinbase WebSockets, 24/7)
   -> Ingestion/Producer (normalize, dedup)
   -> message bus (Redpanda locally / Kinesis on AWS, behind one adapter)
   -> Bytewax stream processor (windowed features: EMA, RSI, VWAP, rolling vol)
        |-> features.out
        \-> lakehouse sink (Parquet/Iceberg) for training + replay
   -> Prediction service: runs N pluggable strategies per feature window
        (momentum, logistic/LightGBM, Kronos, sentiment-LLM, ensemble)
   -> Outcome evaluator: joins each prediction with its realized outcome
        -> live per-strategy accuracy leaderboard + drift/degradation alerts
   -> FastAPI WebSocket hub -> React dashboard (live price, prediction overlays,
        strategy leaderboard, alerts)
```

## What this demonstrates

Real-time/streaming and event-driven architecture, distributed systems, real-time ML
inference, MLOps (training, model registry, online evaluation, drift, retraining),
a lakehouse for training data, performance benchmarking, full-stack delivery, and a
live deployed product on real-world data.

## Layout

- `src/realtime_alpha/core` — shared domain types (Tick, FeatureWindow, Prediction, Alert)
- `src/realtime_alpha/bus` — message-bus interface + adapters (in-memory, Redpanda/Kafka, Kinesis)
- `src/realtime_alpha/strategies` — the `Strategy` protocol, registry, and strategy implementations
- `src/realtime_alpha/ingestion` — Binance WebSocket / REST ingestion
- `src/realtime_alpha/processor` — Bytewax streaming feature computation
- `src/realtime_alpha/prediction` — runs enabled strategies per feature window
- `src/realtime_alpha/evaluation` — online outcome scoring, leaderboard, drift
- `src/realtime_alpha/serving` — FastAPI WebSocket hub + metrics
- `infra/aws`, `infra/fly` — Terraform (production) and Fly config (demo mirror)
- `frontend` — React + Vite dashboard

## Quickstart

Requires **Python 3.12** (the Bytewax stream processor caps at cp312 wheels):

```bash
uv venv --python 3.12 .venv         # or: py -3.12 -m venv .venv
uv pip install -e ".[dev,stream,ingest,serve,ml]"
.venv/Scripts/python -m pytest      # macOS/Linux: .venv/bin/python -m pytest
```

Running the full live stack (Redpanda + services) lands in milestone M1.

## License

MIT
