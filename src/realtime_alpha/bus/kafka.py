"""Kafka/Redpanda bus adapter (aiokafka).

Implements the same ``Bus`` interface as ``MemoryBus`` so ingestion, the predictor, and
serving run unchanged over a real broker. The Bytewax processor uses its own Kafka
source/sink (see ``processor.bytewax_flow``); this adapter is for the asyncio services.
Values are JSON-encoded, matching the codec the Bytewax flow uses.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from .base import Record


class KafkaBus:
    def __init__(self, brokers: str | list[str], *, group_id: str | None = None) -> None:
        self._brokers = brokers if isinstance(brokers, str) else ",".join(brokers)
        self._group_id = group_id
        self._producer: AIOKafkaProducer | None = None

    async def _ensure_producer(self) -> AIOKafkaProducer:
        if self._producer is None:
            self._producer = AIOKafkaProducer(bootstrap_servers=self._brokers)
            await self._producer.start()
        return self._producer

    async def send(self, topic: str, key: str, value: dict[str, Any]) -> None:
        producer = await self._ensure_producer()
        await producer.send_and_wait(
            topic, key=key.encode(), value=json.dumps(value).encode()
        )

    async def stream(self, topic: str, *, from_start: bool = True) -> AsyncIterator[Record]:
        consumer = AIOKafkaConsumer(
            topic,
            bootstrap_servers=self._brokers,
            group_id=self._group_id,
            auto_offset_reset="earliest" if from_start else "latest",
        )
        await consumer.start()
        try:
            async for msg in consumer:
                key = msg.key.decode() if msg.key else ""
                yield Record(topic, key, json.loads(msg.value))
        finally:
            await consumer.stop()

    async def close(self) -> None:
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None
