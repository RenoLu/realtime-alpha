"""The Bytewax streaming feature processor.

This is the production stream-processing engine: a Bytewax dataflow that reads raw
trades from Kafka (Redpanda locally/Fly, MSK on AWS), keys by symbol, runs a stateful
operator holding one ``FeatureEngine`` per symbol, and writes ``FeatureWindow`` records
to ``features.out``.

``feature_pipeline`` is the runtime-agnostic core (operators on domain objects) so it
can be unit-tested with Bytewax's ``TestingSource``/``TestingSink`` without a broker.
``build_kafka_flow`` wraps it with Kafka source/sink + JSON codecs for real runs.

(The lighter ``dataflow.run_feature_processor`` runs the same ``FeatureEngine`` over the
bus abstraction for the single-process embedded mode and broker-free full-pipeline tests.)
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import bytewax.operators as op
from bytewax.dataflow import Dataflow, Stream

from ..bus import FEATURES_OUT, TRADES_RAW
from ..core import FeatureWindow, Tick
from .features import FeatureEngine


def feature_pipeline(
    ticks: Stream[Tick],
    *,
    feature_cfg: dict[str, Any] | None = None,
) -> Stream[tuple[str, FeatureWindow]]:
    """Key ticks by symbol and run a per-symbol stateful FeatureEngine."""
    cfg = feature_cfg or {}
    keyed = op.key_on("by_symbol", ticks, lambda t: t.symbol)
    return op.stateful_map("features", keyed, _make_mapper(cfg))


def _make_mapper(
    cfg: dict[str, Any],
) -> Callable[[FeatureEngine | None, Tick], tuple[FeatureEngine, FeatureWindow]]:
    def mapper(engine: FeatureEngine | None, tick: Tick) -> tuple[FeatureEngine, FeatureWindow]:
        if engine is None:
            engine = FeatureEngine(tick.symbol, **cfg)
        fw = engine.update(tick.price, tick.volume, tick.ts)
        return engine, fw  # non-None state is retained for the next tick of this key

    return mapper


def build_kafka_flow(
    brokers: list[str],
    *,
    in_topic: str = TRADES_RAW,
    out_topic: str = FEATURES_OUT,
    feature_cfg: dict[str, Any] | None = None,
) -> Dataflow:
    """Wire ``feature_pipeline`` to Kafka source/sink with JSON codecs (real runs)."""
    from bytewax.connectors.kafka import KafkaSink, KafkaSinkMessage, KafkaSource

    flow = Dataflow("features")
    raw = op.input("in", flow, KafkaSource(brokers, [in_topic]))
    ticks = op.map("decode", raw, lambda msg: Tick.from_dict(json.loads(msg.value)))
    feats = feature_pipeline(ticks, feature_cfg=feature_cfg)

    def encode(kv: tuple[str, FeatureWindow]) -> KafkaSinkMessage[bytes, bytes]:
        key, fw = kv
        return KafkaSinkMessage(key.encode(), json.dumps(fw.to_dict()).encode())

    msgs = op.map("encode", feats, encode)
    op.output("out", msgs, KafkaSink(brokers, out_topic))
    return flow
