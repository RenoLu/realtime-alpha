"""Core domain types.

These are the messages that flow across the bus, so each one is a frozen,
slotted dataclass with explicit ``to_dict`` / ``from_dict`` JSON codecs. ``from_dict``
tolerates unknown keys so a producer on a newer schema never breaks an older consumer.

All timestamps are epoch **milliseconds** (int), matching exchange WebSocket payloads.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any, Self


def _filter_known(cls: type, data: dict[str, Any]) -> dict[str, Any]:
    """Drop keys the dataclass doesn't declare (forward-compatible decoding)."""
    known = {f.name for f in fields(cls)}
    return {k: v for k, v in data.items() if k in known}


@dataclass(frozen=True, slots=True)
class Tick:
    """A single normalized trade print from an exchange."""

    symbol: str
    price: float
    volume: float
    ts: int  # epoch ms

    def to_dict(self) -> dict[str, Any]:
        return {"symbol": self.symbol, "price": self.price, "volume": self.volume, "ts": self.ts}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(**_filter_known(cls, data))


@dataclass(frozen=True, slots=True)
class FeatureWindow:
    """Streaming features for one symbol at one point in time.

    ``features`` holds named indicators (e.g. ``ema_fast``, ``ema_slow``, ``rsi``,
    ``vwap``, ``ret_1``, ``vol``). ``last_price`` is carried explicitly because both
    strategies and the outcome evaluator need it without digging into ``features``.
    """

    symbol: str
    ts: int  # epoch ms
    last_price: float
    features: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "ts": self.ts,
            "last_price": self.last_price,
            "features": dict(self.features),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        d = _filter_known(cls, data)
        d["features"] = dict(d.get("features") or {})
        return cls(**d)


@dataclass(frozen=True, slots=True)
class Prediction:
    """A forecast from one strategy for one symbol/horizon.

    ``yhat`` is the predicted next-horizon **fractional return** (signed); its sign is
    the directional call. ``confidence`` is in [0, 1]. ``target_ts`` is the timestamp at
    which the prediction can be scored (``ts + horizon_s * 1000``), set by the evaluator.
    """

    symbol: str
    horizon_s: int
    yhat: float
    confidence: float
    strategy_id: str
    ts: int  # epoch ms the prediction was made
    model_ver: str = "v0"
    ref_price: float = 0.0  # price at prediction time; the evaluator scores against it

    @property
    def direction(self) -> int:
        """+1 / -1 / 0 directional call from the sign of ``yhat``."""
        return (self.yhat > 0) - (self.yhat < 0)

    @property
    def target_ts(self) -> int:
        return self.ts + self.horizon_s * 1000

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "horizon_s": self.horizon_s,
            "yhat": self.yhat,
            "confidence": self.confidence,
            "strategy_id": self.strategy_id,
            "ts": self.ts,
            "model_ver": self.model_ver,
            "ref_price": self.ref_price,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(**_filter_known(cls, data))


@dataclass(frozen=True, slots=True)
class Alert:
    """An operational or model-quality alert surfaced to the dashboard."""

    symbol: str
    kind: str  # e.g. "accuracy_degradation", "stale_feed", "drift"
    severity: str  # "info" | "warning" | "critical"
    message: str
    ts: int  # epoch ms

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "kind": self.kind,
            "severity": self.severity,
            "message": self.message,
            "ts": self.ts,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(**_filter_known(cls, data))
