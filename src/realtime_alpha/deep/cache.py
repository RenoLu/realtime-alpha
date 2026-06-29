"""Latest deep-analysis view per symbol, refreshed by the scheduler and read per window."""

from __future__ import annotations

from ..core import DeepView


class DeepViewCache:
    def __init__(self) -> None:
        self._views: dict[str, DeepView] = {}

    def set(self, view: DeepView) -> None:
        self._views[view.symbol] = view

    def get(self, symbol: str) -> DeepView | None:
        return self._views.get(symbol)

    def snapshot(self) -> dict[str, DeepView]:
        return dict(self._views)
