"""Bridge scored outcomes to the dashboard: feed the Leaderboard, broadcast standings.

Consumes ``scores.out``, updates the rolling ``Leaderboard``, and broadcasts the ranked
standings to connected browsers after every score. When a strategy degrades, the alert is
both broadcast (``{type:"alert"}``) and published to ``alerts.out`` for other consumers.
"""

from __future__ import annotations

from collections.abc import Sequence

from ..bus import ALERTS_OUT, SCORES_OUT, Bus
from ..core import Outcome, StrategyStat
from ..evaluation import Leaderboard
from .ws_hub import ConnectionManager


def leaderboard_msg(standings: Sequence[StrategyStat]) -> dict:
    return {"type": "leaderboard", "standings": [s.to_dict() for s in standings]}


async def run_leaderboard_feed(
    bus: Bus,
    manager: ConnectionManager,
    leaderboard: Leaderboard,
    *,
    max_records: int | None = None,
) -> None:
    seen = 0
    async for rec in bus.stream(SCORES_OUT):
        alert = leaderboard.add(Outcome.from_dict(rec.value))
        await manager.broadcast(leaderboard_msg(leaderboard.standings()))
        if alert is not None:
            await manager.broadcast({"type": "alert", **alert.to_dict()})
            await bus.send(ALERTS_OUT, alert.symbol, alert.to_dict())
        seen += 1
        if max_records is not None and seen >= max_records:
            return
