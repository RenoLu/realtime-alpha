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
- `src/realtime_alpha/strategies` — the `Strategy` protocol, registry, and strategies
  (`momentum`, `sentiment_llm`, `ensemble`, `deep_analysis`)
- `src/realtime_alpha/llm` — lean provider-agnostic Claude client (+ deterministic mock)
- `src/realtime_alpha/sentiment` — social-sentiment poller + per-symbol cache
- `src/realtime_alpha/deep` — off-path multi-agent deep-analysis chain + scheduler
- `src/realtime_alpha/dataflows` — vendored market/news/sentiment connectors (from
  [TradingAgents](https://github.com/TauricResearch/TradingAgents), Apache-2.0)
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

### Run it locally

The app can run the whole pipeline in one process over the in-memory bus — live Binance
data → features → predictions → WebSocket → dashboard — so you see real predictions
immediately, no broker required.

```bash
(cd frontend && npm install && npm run build)   # build the React dashboard (once)
realtime-alpha serve --port 8000                 # live pipeline + dashboard
# open http://localhost:8000
```

- Without a frontend build the app still runs and serves a zero-build HTML view.
- `--source ws` uses the exchange WebSocket (needs port 9443 reachable); the default
  REST source pulls the same real market data over HTTPS and works anywhere.

### Strategies & the AI layer

Every feature window is scored by all enabled strategies; the live leaderboard grades them
against realized outcomes. The default lineup:

- **`momentum`** — zero-cost EMA-spread baseline.
- **`sentiment_llm`** — one cheap Claude Haiku call over the features + cached social
  sentiment (StockTwits/Reddit), memoized per snapshot so the hot-path cost stays bounded.
- **`ensemble`** — confidence-weighted blend of the other strategies.
- **`deep_analysis`** — serves a standing view from an off-path, hourly multi-agent chain
  (3 Haiku analyst reads + 1 Opus bull/bear synthesis) that also emits a natural-language
  briefing shown on each dashboard card.
- **`ml_model`** — a **trained LightGBM classifier** on the streaming features.
  `realtime-alpha train` pulls real 1-minute klines, runs them through the *same*
  FeatureEngine the live pipeline uses, labels each bar by its next-bar return, and reports
  **walk-forward out-of-sample** directional accuracy (an honest backtest, not a fit-to-all
  score) before pickling the artifact to `models/`. `serve` auto-loads it if present (else
  the strategy is inert). First run: ~57% OOS directional accuracy over ~2k samples.

The LLM strategies need the `sentiment` extra (`uv pip install -e ".[sentiment]"`) and an
`ANTHROPIC_API_KEY`. **Without a key they degrade gracefully** — a deterministic mock keeps
the pipeline running (momentum stays fully live), so CI and key-less local runs work. The
sentiment poller and deep chain also run standalone: `realtime-alpha sentiment` /
`realtime-alpha deep --once`.

**Model backends** (`llm.py`) are pluggable behind one `ModelClient` seam, chosen by env:
- default: Anthropic API when `ANTHROPIC_API_KEY` is set, else the deterministic mock;
- `RTA_MODEL=agent`: an **agent-authored** backend — `AgentClient` serves per-symbol
  verdicts from a JSON file (`RTA_AGENT_SIGNALS`, default `data/agent_signals.json`) so a
  coding agent can *be* the model when there's no API budget. `sentiment_llm` and
  `deep_analysis` run unchanged; the file is re-read each call (live refresh); missing
  entries fall back to neutral. A ready seed lives at `examples/agent_signals.example.json`
  (`RTA_MODEL=agent RTA_AGENT_SIGNALS=examples/agent_signals.example.json realtime-alpha serve`).
  Authored analyses are graded by the leaderboard against realized prices like any strategy.

### The self-grading leaderboard

The outcome evaluator joins every prediction with the price realized once its horizon
elapses, then a rolling leaderboard ranks each strategy by **live directional accuracy**
(plus MAE and calibration) — the system honestly grading its own predictions on real data,
not a cherry-picked backtest. It surfaces on the dashboard scoreboard, over the WebSocket
(`{type:"leaderboard"}`), and at `GET /api/leaderboard`; a strategy that drops below the
accuracy floor raises an alert. Standalone evaluator service: `realtime-alpha evaluate`.

### Data layer (durable, ~$0)

Persistence is a three-tier, cost-first design — all of it **optional and env-gated** (no
creds ⇒ the app runs purely in-memory as before):

- **Hot** — the bus (in-process MemoryBus, or one Redpanda container). No managed cost.
- **Warm** — **Neon** Postgres (free tier): outcomes + leaderboard snapshots + a model
  registry. Set `RTA_DATABASE_URL` and the leaderboard **survives restarts** (rebuilt from
  the store on startup via `Leaderboard.seed`).
- **Cold** — a Parquet **lakehouse** on **Cloudflare R2** (S3-compatible, free egress),
  written by `realtime-alpha sink`, queried by **DuckDB**:
  `realtime-alpha backtest` prints directional accuracy by strategy over the full history
  (the same store M2's training will read). Set the `RTA_R2_*` vars to enable.

The data is tiny (~155–260 bytes/record), so this stays at **$0/mo** on free tiers. The
identical Parquet layout writes to S3 too: [`infra/aws/`](infra/aws) is a Terraform mirror
(S3 + Iceberg/Glue + Athena) — **validated in CI, applied only on demand** to demo the AWS
architecture, then destroyed. See [`.env.example`](.env.example) for all config.

### Run the full streaming stack (Docker)

The production topology: Redpanda + four services (ingestion → Bytewax processor →
predictor → serving), each from one image, real data flowing through the broker.

```bash
docker compose up --build
# dashboard:        http://localhost:8000
# Redpanda console: http://localhost:8080
```

## License

MIT. The connectors under `src/realtime_alpha/dataflows/` are vendored from
[TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)
(Apache-2.0); see [`NOTICE`](NOTICE) and the license alongside that code.
