"""Bridge the bus to connected browsers: consume predictions, broadcast to clients."""

from __future__ import annotations

from ..bus import PREDICTIONS_OUT, Bus
from .ws_hub import ConnectionManager


async def broadcast_predictions(
    bus: Bus,
    manager: ConnectionManager,
    *,
    max_records: int | None = None,
) -> None:
    sent = 0
    async for rec in bus.stream(PREDICTIONS_OUT):
        await manager.broadcast({"type": "prediction", **rec.value})
        sent += 1
        if max_records is not None and sent >= max_records:
            return
