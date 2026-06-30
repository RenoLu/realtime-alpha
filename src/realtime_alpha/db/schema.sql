-- Operational store for realtime-alpha (Neon/Postgres). Idempotent DDL.

CREATE TABLE IF NOT EXISTS outcomes (
    id              bigserial PRIMARY KEY,
    symbol          text NOT NULL,
    strategy_id     text NOT NULL,
    horizon_s       integer NOT NULL,
    yhat            double precision NOT NULL,
    realized_return double precision NOT NULL,
    hit             boolean NOT NULL,
    abs_error       double precision NOT NULL,
    confidence      double precision NOT NULL,
    ref_price       double precision NOT NULL,
    realized_price  double precision NOT NULL,
    pred_ts         bigint NOT NULL,
    scored_ts       bigint NOT NULL,
    model_ver       text NOT NULL DEFAULT 'v0'
);
CREATE INDEX IF NOT EXISTS outcomes_scored_ts_idx ON outcomes (scored_ts DESC);

CREATE TABLE IF NOT EXISTS leaderboard_snapshots (
    ts        bigint PRIMARY KEY,
    standings jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS model_registry (
    id           bigserial PRIMARY KEY,
    name         text NOT NULL,
    version      text NOT NULL,
    kind         text NOT NULL,
    metrics      jsonb,
    artifact_uri text,
    created_ts   bigint NOT NULL,
    UNIQUE (name, version)
);
