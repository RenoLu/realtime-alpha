"""Streaming feature computation.

``FeatureEngine`` is the incremental, runtime-agnostic core. It runs inside the Bytewax
dataflow (``bytewax_flow``, the production engine over Kafka) and inside the lightweight
bus runner (``dataflow.run_feature_processor``, for embedded mode + broker-free tests).
"""

from __future__ import annotations

from .dataflow import run_feature_processor
from .features import FeatureEngine

__all__ = ["FeatureEngine", "run_feature_processor"]

