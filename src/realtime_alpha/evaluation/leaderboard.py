"""Rolling per-strategy leaderboard + accuracy-degradation alert.

Each strategy keeps a bounded window of recent Outcomes so the standings reflect accuracy
*right now*, not since-inception. ``add`` returns an ``Alert`` the first time a strategy
with enough samples falls below the directional-accuracy floor (hysteresis: it won't
re-fire until the strategy recovers above the floor).
"""

from __future__ import annotations

from collections import defaultdict, deque

from ..core import Alert, Outcome, StrategyStat
from .metrics import calibration_gap, directional_accuracy, mae, mean_confidence


class Leaderboard:
    def __init__(
        self,
        *,
        window: int = 200,
        min_samples: int = 10,
        degrade_floor: float = 0.45,
    ) -> None:
        self._window = window
        self._min_samples = min_samples
        self._degrade_floor = degrade_floor
        self._by_strategy: dict[str, deque[Outcome]] = defaultdict(
            lambda: deque(maxlen=window)
        )
        self._degraded: set[str] = set()  # strategies currently flagged (for hysteresis)

    def add(self, outcome: Outcome) -> Alert | None:
        self._by_strategy[outcome.strategy_id].append(outcome)
        return self._check_degradation(outcome.strategy_id, outcome.scored_ts)

    def _check_degradation(self, strategy_id: str, ts: int) -> Alert | None:
        outs = self._by_strategy[strategy_id]
        if len(outs) < self._min_samples:
            return None
        acc = directional_accuracy(outs)
        if acc >= self._degrade_floor:
            self._degraded.discard(strategy_id)  # recovered -> re-arm
            return None
        if strategy_id in self._degraded:
            return None  # already alerted; stay quiet until recovery
        self._degraded.add(strategy_id)
        return Alert(
            symbol="*",
            kind="accuracy_degradation",
            severity="warning",
            message=(
                f"{strategy_id} directional accuracy {acc:.0%} over last "
                f"{len(outs)} (< {self._degrade_floor:.0%})"
            ),
            ts=ts,
        )

    def standings(self) -> list[StrategyStat]:
        stats = [
            StrategyStat(
                strategy_id=sid,
                n=len(outs),
                dir_acc=directional_accuracy(outs),
                mae=mae(outs),
                mean_confidence=mean_confidence(outs),
                calibration_gap=calibration_gap(outs),
            )
            for sid, outs in self._by_strategy.items()
            if outs
        ]
        stats.sort(key=lambda s: (-s.dir_acc, -s.n))  # best accuracy first, ties by sample count
        return stats
