"""Serialize record batches to Parquet, and write them locally or to R2.

``rows_to_parquet`` uses polars (already a dep via the ml extra). The ``ParquetWriter``
protocol has two implementations: ``LocalWriter`` (a directory, for tests / offline runs)
and ``R2Writer`` (boto3 to any S3-compatible endpoint).
"""

from __future__ import annotations

import io
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol

import polars as pl


def rows_to_parquet(rows: Sequence[dict[str, Any]]) -> bytes:
    buf = io.BytesIO()
    pl.DataFrame(list(rows)).write_parquet(buf)
    return buf.getvalue()


class ParquetWriter(Protocol):
    def write(self, key: str, data: bytes) -> None: ...


class LocalWriter:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def write(self, key: str, data: bytes) -> None:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


class R2Writer:
    """S3-compatible object writer (Cloudflare R2, AWS S3, MinIO, ...)."""

    def __init__(
        self,
        *,
        endpoint: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        client: Any = None,
    ) -> None:
        self.bucket = bucket
        if client is None:
            import boto3  # lazy: only needed for a live R2 target

            client = boto3.client(
                "s3",
                endpoint_url=endpoint,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name="auto",
            )
        self._client = client

    def write(self, key: str, data: bytes) -> None:
        self._client.put_object(Bucket=self.bucket, Key=key, Body=data)


def writer_from_env() -> R2Writer | None:
    """An R2 writer from RTA_R2_* env vars, or None when any is missing (lakehouse off)."""
    endpoint = os.getenv("RTA_R2_ENDPOINT")
    bucket = os.getenv("RTA_R2_BUCKET")
    key = os.getenv("RTA_R2_ACCESS_KEY_ID")
    secret = os.getenv("RTA_R2_SECRET_ACCESS_KEY")
    if not (endpoint and bucket and key and secret):
        return None
    return R2Writer(endpoint=endpoint, bucket=bucket, access_key=key, secret_key=secret)
