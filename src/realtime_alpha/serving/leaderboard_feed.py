"""Bridge scored outcomes to the dashboard: feed the Leaderboard, broadcast standings.

Consumes ``scores.out``, updates the rolling ``Leaderboard``, and broadcasts the ranked
standings to connected browsers after every score. When a strategy degrades, the alert is
both broadcast (``{type:"alert"}``) and published to ``alerts.out`` for other consumers.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..bus import ALERTS_OUT, SCORES_OUT, Bus
from ..core import Outcome, StrategyStat
from ..evaluation import Leaderboard
from .ws_hub import ConnectionManager


def leaderboard_msg(standings: Sequence[StrategyStat]) -> dict:
    return {"type": "leaderboard", "standings": [s.to_dict() for s in standings]}


async def _persist(store: Any, outcome: Outcome, leaderboard: Leaderboard, snapshot: bool) -> None:
    """Best-effort durable writes; a DB hiccup must never stall the live feed."""
    try:
        await store.record_outcome(outcome)
        if snapshot:
            await store.save_leaderboard(leaderboard.standings(), outcome.scored_ts)
    except Exception:  # noqa: BLE001 - operational store is optional / best-effort
        pass


async def run_leaderboard_feed(
    bus: Bus,
    manager: ConnectionManager,
    leaderboard: Leaderboard,
    *,
    store: Any = None,
    snapshot_every: int = 20,
    max_records: int | None = None,
) -> None:
    seen = 0
    async for rec in bus.stream(SCORES_OUT):
        outcome = Outcome.from_dict(rec.value)
        alert = leaderboard.add(outcome)
        await manager.broadcast(leaderboard_msg(leaderboard.standings()))
        if alert is not None:
            await manager.broadcast({"type": "alert", **alert.to_dict()})
            await bus.send(ALERTS_OUT, alert.symbol, alert.to_dict())
        seen += 1
        if store is not None:
            await _persist(store, outcome, leaderboard, snapshot=(seen % snapshot_every == 0))
        if max_records is not None and seen >= max_records:
            return
