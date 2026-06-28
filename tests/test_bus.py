from realtime_alpha.bus import (
    ALERTS_OUT,
    FEATURES_OUT,
    KLINES_RAW,
    PREDICTIONS_OUT,
    TRADES_RAW,
    MemoryBus,
)


def test_topic_constants_are_distinct():
    assert len({TRADES_RAW, KLINES_RAW, FEATURES_OUT, PREDICTIONS_OUT, ALERTS_OUT}) == 5


async def test_send_then_history_round_trips_topic_key_and_value():
    bus = MemoryBus()
    await bus.send(TRADES_RAW, "BTCUSDT", {"price": 1.0})
    (rec,) = bus.history(TRADES_RAW)
    assert rec.topic == TRADES_RAW
    assert rec.key == "BTCUSDT"
    assert rec.value == {"price": 1.0}


async def test_history_preserves_per_key_order():
    bus = MemoryBus()
    for price in (1, 2, 3):
        await bus.send(TRADES_RAW, "BTCUSDT", {"price": price})
    assert [r.value["price"] for r in bus.history(TRADES_RAW)] == [1, 2, 3]


async def test_stored_value_is_isolated_from_caller_mutation():
    bus = MemoryBus()
    payload = {"price": 1.0}
    await bus.send(TRADES_RAW, "BTCUSDT", payload)
    payload["price"] = 999.0
    assert bus.history(TRADES_RAW)[0].value == {"price": 1.0}


async def test_stream_replays_history_then_yields_live_records():
    bus = MemoryBus()
    await bus.send(FEATURES_OUT, "BTCUSDT", {"v": 1})

    agen = bus.stream(FEATURES_OUT)
    first = await anext(agen)  # replayed from history
    await bus.send(FEATURES_OUT, "BTCUSDT", {"v": 2})
    second = await anext(agen)  # delivered live

    assert [first.value["v"], second.value["v"]] == [1, 2]
