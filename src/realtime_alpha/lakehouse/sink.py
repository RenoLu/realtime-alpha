"""The lakehouse sink: batch bus records into Hive-partitioned Parquet.

Runs one consumer per analytical topic, buffers rows per partition, and flushes a Parquet
object when a buffer fills (``batch_size``) or on a timer (``flush_interval``) -- so
low-volume partitions still land promptly. Blocking writes go through ``asyncio.to_thread``
so the event loop stays responsive. ``max_records`` bounds it for tests.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from ..bus import FEATURES_OUT, PREDICTIONS_OUT, SCORES_OUT, Bus
from .parquet import ParquetWriter, rows_to_parquet
from .partition import Partition, partition_for

_DEFAULT_TOPICS = (FEATURES_OUT, PREDICTIONS_OUT, SCORES_OUT)


def _flatten(value: dict[str, Any]) -> dict[str, Any]:
    """Lift a nested ``features`` dict into top-level columns for clean columnar Parquet."""
    feats = value.get("features")
    if not isinstance(feats, dict):
        return value
    return {**{k: v for k, v in value.items() if k != "features"}, **feats}


async def run_lakehouse_sink(
    bus: Bus,
    writer: ParquetWriter,
    *,
    topics: Sequence[str] = _DEFAULT_TOPICS,
    batch_size: int = 200,
    flush_interval: float = 30.0,
    max_records: int | None = None,
) -> None:
    buffers: dict[Partition, list[dict[str, Any]]] = defaultdict(list)
    seq = 0
    consumed = 0
    done = asyncio.Event()

    async def flush(partition: Partition) -> None:
        nonlocal seq
        rows = buffers.get(partition)
        if not rows:
            return
        buffers[partition] = []
        seq += 1
        last_ts = rows[-1].get("ts") or rows[-1].get("scored_ts") or 0
        key = f"{partition.prefix}/part-{last_ts}-{seq}.parquet"
        await asyncio.to_thread(writer.write, key, rows_to_parquet(rows))

    async def flush_all() -> None:
        for partition in list(buffers):
            await flush(partition)

    async def consume(topic: str) -> None:
        nonlocal consumed
        async for rec in bus.stream(topic):
            partition = partition_for(rec.topic, rec.value)
            if partition is not None:
                buffers[partition].append(_flatten(rec.value))
                if len(buffers[partition]) >= batch_size:
                    await flush(partition)
            consumed += 1
            if max_records is not None and consumed >= max_records:
                done.set()
                return

    async def ticker() -> None:
        while not done.is_set():
            await asyncio.sleep(flush_interval)
            await flush_all()

    consumers = [asyncio.create_task(consume(t)) for t in topics]
    tick = asyncio.create_task(ticker())
    try:
        if max_records is not None:
            await done.wait()
        else:
            await asyncio.gather(*consumers)
    finally:
        for c in consumers:
            c.cancel()
        tick.cancel()
        await flush_all()  # don't lose a partial batch on shutdown
