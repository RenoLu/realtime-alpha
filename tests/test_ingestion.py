from collections.abc import AsyncIterator

from realtime_alpha.bus import TRADES_RAW, MemoryBus
from realtime_alpha.core import Tick
from realtime_alpha.ingestion.normalize import normalize_binance_trade
from realtime_alpha.ingestion.producer import run_ingestion
from realtime_alpha.ingestion.rest_poll import binance_rest_to_payload


def _trade(*, t: int, p: float, s: str = "BTCUSDT", ts: int = 1700) -> dict:
    """A Binance @trade payload (the `data` object of a combined-stream message)."""
    return {"e": "trade", "s": s, "t": t, "p": str(p), "q": "0.25", "T": ts}


async def _source(items: list[dict]) -> AsyncIterator[dict]:
    for it in items:
        yield it


def test_normalize_binance_trade_maps_fields_and_casts_numbers():
    tick = normalize_binance_trade(_trade(t=42, p=65000.5, s="ETHUSDT", ts=1700))
    assert tick == Tick("ETHUSDT", 65000.5, 0.25, 1700)


async def test_ingestion_normalizes_and_produces_to_trades_raw_keyed_by_symbol():
    bus = MemoryBus()
    await run_ingestion(bus, _source([_trade(t=1, p=100.0), _trade(t=2, p=101.0)]))

    recs = bus.history(TRADES_RAW)
    assert [r.key for r in recs] == ["BTCUSDT", "BTCUSDT"]
    assert [Tick.from_dict(r.value).price for r in recs] == [100.0, 101.0]


def test_binance_rest_trade_maps_to_the_same_payload_shape_as_ws():
    # The REST fallback must yield the exact shape the WS source does, so the producer
    # and normalizer stay source-agnostic.
    rest_trade = {"id": 7, "price": "100.5", "qty": "0.5", "time": 1700, "isBuyerMaker": True}
    payload = binance_rest_to_payload("BTCUSDT", rest_trade)
    assert payload == {"s": "BTCUSDT", "t": 7, "p": "100.5", "q": "0.5", "T": 1700}
    assert normalize_binance_trade(payload) == Tick("BTCUSDT", 100.5, 0.5, 1700)


async def test_ingestion_dedups_repeated_trade_ids_per_symbol():
    bus = MemoryBus()
    await run_ingestion(
        bus, _source([_trade(t=1, p=100.0), _trade(t=1, p=100.0), _trade(t=2, p=101.0)])
    )

    prices = [Tick.from_dict(r.value).price for r in bus.history(TRADES_RAW)]
    assert prices == [100.0, 101.0]  # the duplicate t=1 is dropped
