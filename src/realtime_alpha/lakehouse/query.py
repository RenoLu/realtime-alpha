"""Query the Parquet lakehouse with DuckDB (backtest / replay / training reads).

``connect()`` returns a DuckDB connection; pass ``r2=`` to wire an S3-compatible secret so
``read_parquet('s3://bucket/...')`` reads R2 directly. ``root`` is a local dir (tests /
offline) or ``s3://<bucket>``; datasets are Hive-partitioned (``dt=``/``symbol=``).
"""

from __future__ import annotations

import os
from typing import Any

import duckdb


def r2_config_from_env() -> dict[str, str] | None:
    """R2 connection config from RTA_R2_* env vars, or None (query local paths only)."""
    endpoint = os.getenv("RTA_R2_ENDPOINT")
    key = os.getenv("RTA_R2_ACCESS_KEY_ID")
    secret = os.getenv("RTA_R2_SECRET_ACCESS_KEY")
    if not (endpoint and key and secret):
        return None
    return {"endpoint": endpoint, "access_key": key, "secret_key": secret}


def connect(*, r2: dict[str, str] | None = None) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    if r2:
        con.execute("INSTALL httpfs; LOAD httpfs;")
        endpoint = r2["endpoint"].removeprefix("https://").removeprefix("http://").rstrip("/")
        con.execute(
            "CREATE SECRET rta_r2 (TYPE S3, KEY_ID ?, SECRET ?, ENDPOINT ?, URL_STYLE 'path', USE_SSL true)",
            [r2["access_key"], r2["secret_key"], endpoint],
        )
    return con


def _glob(root: str, dataset: str) -> str:
    return f"{root.rstrip('/')}/{dataset}/**/*.parquet"


def accuracy_by_strategy(con: duckdb.DuckDBPyConnection, root: str) -> list[dict[str, Any]]:
    """Directional accuracy / MAE per strategy over the full outcome history."""
    sql = """
        SELECT strategy_id,
               count(*)                                AS n,
               avg(CASE WHEN hit THEN 1.0 ELSE 0.0 END) AS dir_acc,
               avg(abs_error)                          AS mae
        FROM read_parquet(?, hive_partitioning=true)
        GROUP BY strategy_id
        ORDER BY dir_acc DESC, n DESC
    """
    cols = ["strategy_id", "n", "dir_acc", "mae"]
    return [dict(zip(cols, row, strict=True)) for row in con.execute(sql, [_glob(root, "outcomes")]).fetchall()]
