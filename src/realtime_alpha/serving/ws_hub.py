"""WebSocket connection manager: fan a message out to all connected browsers.

Works with any object exposing ``async send_text(str)`` (a Starlette WebSocket in
production, a fake in tests). A connection that errors on send is evicted so one dead
browser can't block the broadcast.
"""

from __future__ import annotations

import json
from typing import Any, Protocol


class _WSLike(Protocol):
    async def send_text(self, data: str) -> None: ...


class ConnectionManager:
    def __init__(self) -> None:
        self._active: set[_WSLike] = set()

    def connect(self, ws: _WSLike) -> None:
        self._active.add(ws)

    def disconnect(self, ws: _WSLike) -> None:
        self._active.discard(ws)

    @property
    def count(self) -> int:
        return len(self._active)

    async def broadcast(self, message: dict[str, Any]) -> None:
        data = json.dumps(message)
        dead: list[_WSLike] = []
        for ws in list(self._active):
            try:
                await ws.send_text(data)
            except Exception:  # noqa: BLE001 - any send failure means the client is gone
                dead.append(ws)
        for ws in dead:
            self._active.discard(ws)
