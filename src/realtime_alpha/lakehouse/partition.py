"""Decide where a bus record lands in the lakehouse: dataset + Hive partition.

Pure (no IO) so the layout is unit-testable. Only the analytical topics are persisted;
raw trades/klines and alerts are skipped.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ..bus import FEATURES_OUT, PREDICTIONS_OUT, SCORES_OUT

_TOPIC_DATASET = {
    FEATURES_OUT: "features",
    PREDICTIONS_OUT: "predictions",
    SCORES_OUT: "outcomes",
}


@dataclass(frozen=True, slots=True)
class Partition:
    dataset: str
    dt: str  # YYYY-MM-DD (UTC)
    symbol: str

    @property
    def prefix(self) -> str:
        return f"{self.dataset}/dt={self.dt}/symbol={self.symbol}"


def partition_for(topic: str, value: dict[str, Any]) -> Partition | None:
    """The partition for ``value`` on ``topic``, or ``None`` if the topic isn't persisted."""
    dataset = _TOPIC_DATASET.get(topic)
    if dataset is None:
        return None
    symbol = value.get("symbol", "UNKNOWN")
    ts = value.get("ts") or value.get("scored_ts") or value.get("pred_ts") or 0
    dt = datetime.fromtimestamp(ts / 1000, tz=UTC).strftime("%Y-%m-%d")
    return Partition(dataset=dataset, dt=dt, symbol=symbol)
