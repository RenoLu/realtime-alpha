"""Offline ML: build a labelled dataset from streaming features, train a walk-forward
model, and serve it as a Strategy. Reuses the live FeatureEngine so train- and serve-time
features are identical.
"""

from __future__ import annotations

from .dataset import DEFAULT_FEATURE_COLS, build_dataset, features_to_vector

__all__ = ["DEFAULT_FEATURE_COLS", "build_dataset", "features_to_vector"]
