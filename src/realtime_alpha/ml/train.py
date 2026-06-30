"""Offline trainer: real klines -> live FeatureEngine -> walk-forward LightGBM -> artifact.

The label is the sign of the next-bar return (see ``dataset.build_dataset``). Accuracy is
reported **out-of-sample** across expanding-window folds — an honest backtest, not a
fit-to-everything score. The final model is fit on all data and pickled with its feature
columns + metrics for ``MLModelStrategy`` to serve.
"""

from __future__ import annotations

import pickle
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

from ..core import FeatureWindow
from ..processor.features import FeatureEngine
from .dataset import build_dataset

_BINANCE_KLINES = "https://api.binance.us/api/v3/klines"


def fetch_klines(
    symbol: str, *, interval: str = "1m", limit: int = 1000, client: Any = None
) -> list[tuple[int, float, float]]:
    """Recent klines as (close_time_ms, close, volume)."""
    if client is None:
        import httpx

        client = httpx
    resp = client.get(
        _BINANCE_KLINES, params={"symbol": symbol, "interval": interval, "limit": limit}, timeout=20
    )
    resp.raise_for_status()
    return [(int(k[6]), float(k[4]), float(k[5])) for k in resp.json()]


def windows_from_klines(
    symbol: str, klines: Sequence[tuple[int, float, float]], *, cfg: dict[str, int] | None = None
) -> list[FeatureWindow]:
    engine = FeatureEngine(symbol, **(cfg or {}))
    return [engine.update(price=close, volume=vol, ts=ts) for ts, close, vol in klines]


def fold_bounds(n: int, *, n_splits: int = 5) -> Iterator[tuple[int, int]]:
    """Expanding-window (train_end, test_end) bounds: fold k trains on [0:k*f), tests [k*f:(k+1)*f)."""
    fold = n // (n_splits + 1)
    for k in range(1, n_splits + 1):
        yield fold * k, fold * (k + 1)


def _fit(x: Sequence[Sequence[float]], y: Sequence[int]) -> Any:
    import numpy as np
    from lightgbm import LGBMClassifier

    model = LGBMClassifier(
        n_estimators=120, num_leaves=15, learning_rate=0.05, min_child_samples=20, verbose=-1
    )
    # Fit on an ndarray (no column names) so serving can predict on a plain list without a
    # "feature names" warning on every prediction.
    model.fit(np.asarray(x, dtype=float), np.asarray(y))
    return model


def walk_forward(x: list[list[float]], y: list[int], *, n_splits: int = 5) -> list[float]:
    """Out-of-sample directional accuracy per expanding-window fold."""
    accs: list[float] = []
    for train_end, test_end in fold_bounds(len(x), n_splits=n_splits):
        xtr, ytr = x[:train_end], y[:train_end]
        xte, yte = x[train_end:test_end], y[train_end:test_end]
        if len(set(ytr)) < 2 or not xte:
            continue
        model = _fit(xtr, ytr)
        preds = [1 if p[1] >= 0.5 else 0 for p in model.predict_proba(xte)]
        accs.append(sum(int(a == b) for a, b in zip(preds, yte, strict=True)) / len(yte))
    return accs


def train_model(
    symbols: Sequence[str],
    *,
    interval: str = "1m",
    limit: int = 1000,
    horizon: int = 1,
    n_splits: int = 5,
    cfg: dict[str, int] | None = None,
) -> tuple[Any, list[str], dict[str, Any]]:
    x: list[list[float]] = []
    y: list[int] = []
    cols: list[str] = []
    for symbol in symbols:  # label within each symbol, then pool (no cross-symbol labels)
        windows = windows_from_klines(symbol, fetch_klines(symbol, interval=interval, limit=limit), cfg=cfg)
        xi, yi, cols = build_dataset(windows, horizon=horizon)
        x += xi
        y += yi
    accs = walk_forward(x, y, n_splits=n_splits)
    model = _fit(x, y)
    metrics = {
        "oos_dir_acc": sum(accs) / len(accs) if accs else None,
        "folds": [round(a, 4) for a in accs],
        "n": len(x),
        "symbols": list(symbols),
    }
    return model, cols, metrics


def save_artifact(
    model: Any, feature_cols: Sequence[str], path: str, *, model_ver: str = "ml-v0", metrics: dict | None = None
) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(
            {"model": model, "feature_cols": list(feature_cols), "model_ver": model_ver, "metrics": metrics},
            f,
        )
