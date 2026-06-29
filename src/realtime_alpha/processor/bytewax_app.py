"""Module-level Bytewax flow for `python -m bytewax.run realtime_alpha.processor.bytewax_app:flow`.

Brokers and topics come from the environment so the same image serves any deployment.
"""

from __future__ import annotations

import os

from .bytewax_flow import build_kafka_flow

_brokers = os.getenv("RTA_BROKERS", "localhost:9092").split(",")

flow = build_kafka_flow(_brokers)
