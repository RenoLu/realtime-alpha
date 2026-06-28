"""Pluggable prediction strategies + their registry.

Importing this package registers the built-in strategies (so ``registered_ids()`` is
populated). Additional strategies (logistic/LightGBM, Kronos, sentiment-LLM, ensemble)
register themselves the same way as they land.
"""

from __future__ import annotations

from . import momentum  # noqa: F401  -- import for @register side effect
from .base import Strategy
from .registry import enabled_strategies, get_strategy, register, registered_ids

__all__ = [
    "Strategy",
    "enabled_strategies",
    "get_strategy",
    "register",
    "registered_ids",
]
