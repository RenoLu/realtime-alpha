"""Online outcome evaluation: join predictions with realized prices, score, rank.

The self-grading layer. The evaluator joins each prediction with the price observed once
its horizon elapsed (`evaluator.py`), scores it (`metrics.py`), and a rolling leaderboard
(`leaderboard.py`) ranks each strategy by live directional accuracy.
"""

from __future__ import annotations

from .evaluator import OutcomeJoiner, run_evaluator
from .leaderboard import Leaderboard
from .metrics import (
    calibration_gap,
    directional_accuracy,
    mae,
    mean_confidence,
    score_prediction,
)

__all__ = [
    "Leaderboard",
    "OutcomeJoiner",
    "calibration_gap",
    "directional_accuracy",
    "mae",
    "mean_confidence",
    "run_evaluator",
    "score_prediction",
]
