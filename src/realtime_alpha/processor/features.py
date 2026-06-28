"""Incremental, per-symbol streaming features.

Everything updates in O(1) (or O(window)) per tick — no recomputation over history —
which is what makes this viable as a real-time stream operator. One ``FeatureEngine``
holds the rolling state for a single symbol; the dataflow keeps one per symbol.

History-derived features (``ret_1``, ``vol``, ``rsi``) only appear once there is enough
history to compute them, so downstream strategies can simply check for their presence.
"""

from __future__ import annotations

from collections import deque
from statistics import pstdev

from ..core import FeatureWindow


class FeatureEngine:
    def __init__(
        self,
        symbol: str,
        *,
        ema_fast: int = 12,
        ema_slow: int = 26,
        rsi_period: int = 14,
        vol_window: int = 20,
    ) -> None:
        self.symbol = symbol
        self._alpha_fast = 2.0 / (ema_fast + 1)
        self._alpha_slow = 2.0 / (ema_slow + 1)
        self._rsi_period = rsi_period

        self._ema_fast: float | None = None
        self._ema_slow: float | None = None
        self._prev_price: float | None = None
        self._returns: deque[float] = deque(maxlen=vol_window)

        # Running volume-weighted average price.
        self._cum_pv = 0.0
        self._cum_v = 0.0

        # Wilder RSI state: seed from a simple average of the first ``rsi_period``
        # deltas, then smooth.
        self._seed_gains: list[float] = []
        self._seed_losses: list[float] = []
        self._avg_gain: float | None = None
        self._avg_loss: float | None = None

    def update(self, price: float, volume: float, ts: int) -> FeatureWindow:
        features: dict[str, float] = {}

        # EMAs (seed to the first price).
        if self._ema_fast is None or self._ema_slow is None:
            self._ema_fast = price
            self._ema_slow = price
        else:
            self._ema_fast = self._alpha_fast * price + (1 - self._alpha_fast) * self._ema_fast
            self._ema_slow = self._alpha_slow * price + (1 - self._alpha_slow) * self._ema_slow
        features["ema_fast"] = self._ema_fast
        features["ema_slow"] = self._ema_slow

        # Running VWAP.
        self._cum_pv += price * volume
        self._cum_v += volume
        if self._cum_v > 0:
            features["vwap"] = self._cum_pv / self._cum_v

        # Return-derived features.
        if self._prev_price is not None and self._prev_price != 0:
            ret = price / self._prev_price - 1.0
            features["ret_1"] = ret
            self._returns.append(ret)
            if len(self._returns) >= 2:
                features["vol"] = pstdev(self._returns)

            rsi = self._update_rsi(price - self._prev_price)
            if rsi is not None:
                features["rsi"] = rsi

        self._prev_price = price
        return FeatureWindow(symbol=self.symbol, ts=ts, last_price=price, features=features)

    def _update_rsi(self, delta: float) -> float | None:
        gain = max(delta, 0.0)
        loss = max(-delta, 0.0)
        if self._avg_gain is None or self._avg_loss is None:
            self._seed_gains.append(gain)
            self._seed_losses.append(loss)
            if len(self._seed_gains) < self._rsi_period:
                return None
            self._avg_gain = sum(self._seed_gains) / self._rsi_period
            self._avg_loss = sum(self._seed_losses) / self._rsi_period
        else:
            n = self._rsi_period
            self._avg_gain = (self._avg_gain * (n - 1) + gain) / n
            self._avg_loss = (self._avg_loss * (n - 1) + loss) / n

        if self._avg_loss == 0:
            return 100.0
        rs = self._avg_gain / self._avg_loss
        return 100.0 - 100.0 / (1.0 + rs)
