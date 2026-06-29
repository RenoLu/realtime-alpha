"""FastAPI serving tier: WebSocket fan-out of live predictions to the dashboard."""

from __future__ import annotations

from .broadcaster import broadcast_predictions
from .ws_hub import ConnectionManager

__all__ = ["ConnectionManager", "broadcast_predictions"]
