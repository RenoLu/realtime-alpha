"""The message-bus seam.

Every service talks to the bus through this interface, never to a broker directly.
That lets the same processing code run on **Redpanda** (local/CI/Fly) and **Kinesis**
(AWS) by swapping the adapter — ports-and-adapters at the infrastructure boundary.
``MemoryBus`` is the in-process adapter used by tests and single-process local runs.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

# Topic names (the bus partitions by key = symbol).
TRADES_RAW = "trades.raw"
KLINES_RAW = "klines.raw"
FEATURES_OUT = "features.out"
PREDICTIONS_OUT = "predictions.out"
SCORES_OUT = "scores.out"
ALERTS_OUT = "alerts.out"

ALL_TOPICS = (TRADES_RAW, KLINES_RAW, FEATURES_OUT, PREDICTIONS_OUT, SCORES_OUT, ALERTS_OUT)


@dataclass(frozen=True, slots=True)
class Record:
    topic: str
    key: str
    value: dict[str, Any]


@runtime_checkable
class Bus(Protocol):
    async def send(self, topic: str, key: str, value: dict[str, Any]) -> None:
        """Publish ``value`` to ``topic`` partitioned by ``key``."""
        ...

    def stream(self, topic: str, *, from_start: bool = True) -> AsyncIterator[Record]:
        """Yield records from ``topic`` (optionally replaying existing ones first)."""
        ...
