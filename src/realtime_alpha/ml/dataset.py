"""Turn a sequence of FeatureWindows into a supervised (X, y) dataset.

Pure (no IO) so the labelling is unit-testable. ``y`` is the sign of the realized return
``horizon`` windows ahead (a directional classification target); warmup rows that lack any
feature column, and the final ``horizon`` rows that have no future, are dropped.
"""

from __future__ import annotations

from collections.abc import Sequence

from ..core import FeatureWindow

# The features the live FeatureEngine emits after warmup — train and serve on the same set.
DEFAULT_FEATURE_COLS = ("ema_fast", "ema_slow", "rsi", "vol", "ret_1", "vwap")


def features_to_vector(features: dict[str, float], cols: Sequence[str]) -> list[float]:
    return [float(features.get(c, 0.0)) for c in cols]


def build_dataset(
    windows: Sequence[FeatureWindow],
    *,
    horizon: int = 1,
    feature_cols: Sequence[str] = DEFAULT_FEATURE_COLS,
) -> tuple[list[list[float]], list[int], list[str]]:
    cols = list(feature_cols)
    x: list[list[float]] = []
    y: list[int] = []
    for i in range(len(windows) - horizon):
        w = windows[i]
        if w.last_price <= 0 or any(c not in w.features for c in cols):
            continue  # warmup / unusable row
        future_ret = (windows[i + horizon].last_price - w.last_price) / w.last_price
        x.append(features_to_vector(w.features, cols))
        y.append(1 if future_ret > 0 else 0)
    return x, y, cols
