"""Latest sentiment snapshot per symbol, refreshed by the poller, read per window."""

from __future__ import annotations

from ..core import SentimentSnapshot


class SentimentCache:
    def __init__(self) -> None:
        self._snaps: dict[str, SentimentSnapshot] = {}

    def set(self, snap: SentimentSnapshot) -> None:
        self._snaps[snap.symbol] = snap

    def get(self, symbol: str) -> SentimentSnapshot | None:
        return self._snaps.get(symbol)

    def snapshot(self) -> dict[str, SentimentSnapshot]:
        return dict(self._snaps)
