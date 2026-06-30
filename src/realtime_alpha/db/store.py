"""Operational Postgres store (Neon free tier): outcomes + leaderboard + model registry.

The ``Outcome <-> row`` mapping is pure and unit-tested; ``OutcomeStore`` wraps an asyncpg
pool (imported lazily, so the mapping is usable without the lakehouse extra). The store is
optional everywhere -- callers build it only when ``RTA_DATABASE_URL`` is set.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ..core import Outcome, StrategyStat

OUTCOME_COLS = (
    "symbol", "strategy_id", "horizon_s", "yhat", "realized_return", "hit",
    "abs_error", "confidence", "ref_price", "realized_price", "pred_ts", "scored_ts", "model_ver",
)

_SCHEMA = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")
_INSERT = (
    f"INSERT INTO outcomes ({', '.join(OUTCOME_COLS)}) "
    f"VALUES ({', '.join(f'${i + 1}' for i in range(len(OUTCOME_COLS)))})"
)
_RECENT = (
    f"SELECT {', '.join(OUTCOME_COLS)} FROM outcomes ORDER BY scored_ts DESC, id DESC LIMIT $1"
)


def outcome_to_row(o: Outcome) -> tuple[Any, ...]:
    return tuple(getattr(o, col) for col in OUTCOME_COLS)


def row_to_outcome(row: Mapping[str, Any]) -> Outcome:
    return Outcome(**{col: row[col] for col in OUTCOME_COLS})


class OutcomeStore:
    def __init__(self, pool: Any) -> None:
        self._pool = pool

    @classmethod
    async def connect(cls, dsn: str) -> OutcomeStore:
        import asyncpg  # lazy: only needed for a live DB

        pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4)
        store = cls(pool)
        await store.init()
        return store

    async def init(self) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(_SCHEMA)

    async def record_outcome(self, outcome: Outcome) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(_INSERT, *outcome_to_row(outcome))

    async def recent_outcomes(self, limit: int = 200) -> list[Outcome]:
        """The most recent ``limit`` outcomes, returned oldest-first (replay order)."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(_RECENT, limit)
        return [row_to_outcome(r) for r in reversed(rows)]

    async def save_leaderboard(self, standings: Sequence[StrategyStat], ts: int) -> None:
        payload = json.dumps([s.to_dict() for s in standings])
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO leaderboard_snapshots (ts, standings) VALUES ($1, $2::jsonb) "
                "ON CONFLICT (ts) DO UPDATE SET standings = EXCLUDED.standings",
                ts, payload,
            )

    async def register_model(
        self, *, name: str, version: str, kind: str, metrics: dict[str, Any], artifact_uri: str, ts: int
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO model_registry (name, version, kind, metrics, artifact_uri, created_ts) "
                "VALUES ($1, $2, $3, $4::jsonb, $5, $6) ON CONFLICT (name, version) DO NOTHING",
                name, version, kind, json.dumps(metrics), artifact_uri, ts,
            )

    async def close(self) -> None:
        await self._pool.close()
