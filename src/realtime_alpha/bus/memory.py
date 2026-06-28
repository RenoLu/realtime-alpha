"""In-process bus adapter for unit tests and single-process local runs."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from typing import Any

from .base import Record


class MemoryBus:
    """Records are appended to a per-topic log and fanned out to live subscribers.

    ``stream`` optionally replays the existing log before yielding new records, which
    mirrors a Kafka/Redpanda consumer reading from the earliest offset.
    """

    def __init__(self) -> None:
        self._log: dict[str, list[Record]] = defaultdict(list)
        self._subscribers: dict[str, list[asyncio.Queue[Record]]] = defaultdict(list)

    async def send(self, topic: str, key: str, value: dict[str, Any]) -> None:
        rec = Record(topic, key, dict(value))  # copy so later caller mutation can't leak in
        self._log[topic].append(rec)
        for q in self._subscribers[topic]:
            q.put_nowait(rec)

    def history(self, topic: str) -> list[Record]:
        return list(self._log[topic])

    async def stream(self, topic: str, *, from_start: bool = True) -> AsyncIterator[Record]:
        q: asyncio.Queue[Record] = asyncio.Queue()
        if from_start:
            for rec in self._log[topic]:
                q.put_nowait(rec)
        self._subscribers[topic].append(q)
        try:
            while True:
                yield await q.get()
        finally:
            self._subscribers[topic].remove(q)
