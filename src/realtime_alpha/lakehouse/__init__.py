"""Durable data layer: a Parquet lakehouse on object storage, queried by DuckDB.

The bus sink (`sink.py`) batches features/predictions/outcomes into Hive-partitioned
Parquet (`partition.py` decides the layout; `parquet.py` writes it locally or to R2);
`query.py` reads it back with DuckDB for backtest/replay/training. Everything is env-gated:
with no object-store creds the app runs exactly as before.
"""

from __future__ import annotations

from .parquet import LocalWriter, ParquetWriter, R2Writer, rows_to_parquet, writer_from_env
from .partition import Partition, partition_for
from .query import accuracy_by_strategy, connect, r2_config_from_env
from .sink import run_lakehouse_sink

__all__ = [
    "LocalWriter",
    "Partition",
    "ParquetWriter",
    "R2Writer",
    "accuracy_by_strategy",
    "connect",
    "partition_for",
    "r2_config_from_env",
    "rows_to_parquet",
    "run_lakehouse_sink",
    "writer_from_env",
]
