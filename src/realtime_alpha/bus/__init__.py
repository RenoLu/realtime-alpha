"""Message-bus interface + adapters (in-memory now; Redpanda/Kafka and Kinesis land with ingestion)."""

from __future__ import annotations

from .base import (
    ALERTS_OUT,
    ALL_TOPICS,
    FEATURES_OUT,
    KLINES_RAW,
    PREDICTIONS_OUT,
    TRADES_RAW,
    Bus,
    Record,
)
from .memory import MemoryBus

__all__ = [
    "ALERTS_OUT",
    "ALL_TOPICS",
    "FEATURES_OUT",
    "KLINES_RAW",
    "PREDICTIONS_OUT",
    "TRADES_RAW",
    "Bus",
    "MemoryBus",
    "Record",
]
