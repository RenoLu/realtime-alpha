"""The prediction tier: runs enabled strategies on feature windows and emits predictions."""

from __future__ import annotations

from .service import run_predictor

__all__ = ["run_predictor"]
