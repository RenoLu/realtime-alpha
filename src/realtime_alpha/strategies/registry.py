"""A tiny decorator-based registry so strategies self-register and config selects them."""

from __future__ import annotations

from .base import Strategy

_REGISTRY: dict[str, type[Strategy]] = {}


def register(cls: type[Strategy]) -> type[Strategy]:
    """Class decorator: register a strategy by its ``id``."""
    _REGISTRY[cls.id] = cls
    return cls


def registered_ids() -> list[str]:
    return sorted(_REGISTRY)


def get_strategy(strategy_id: str) -> Strategy:
    """Instantiate a registered strategy with its defaults. Raises KeyError if unknown."""
    return _REGISTRY[strategy_id]()


def enabled_strategies(ids: list[str]) -> list[Strategy]:
    """Instantiate the strategies named in config, preserving order."""
    return [get_strategy(i) for i in ids]
