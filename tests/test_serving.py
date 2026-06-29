from fastapi.testclient import TestClient

from realtime_alpha.bus import PREDICTIONS_OUT, MemoryBus
from realtime_alpha.serving.app import create_app
from realtime_alpha.serving.broadcaster import broadcast_predictions
from realtime_alpha.serving.ws_hub import ConnectionManager


class FakeWS:
    """Duck-typed stand-in for a Starlette WebSocket (only ``send_text`` is used)."""

    def __init__(self, *, fail: bool = False) -> None:
        self.sent: list[str] = []
        self._fail = fail

    async def send_text(self, data: str) -> None:
        if self._fail:
            raise RuntimeError("connection closed")
        self.sent.append(data)


async def test_broadcast_delivers_json_to_every_connection():
    mgr = ConnectionManager()
    a, b = FakeWS(), FakeWS()
    mgr.connect(a)
    mgr.connect(b)

    await mgr.broadcast({"hello": 1})

    assert a.sent == ['{"hello": 1}']
    assert b.sent == ['{"hello": 1}']


async def test_disconnect_stops_delivery():
    mgr = ConnectionManager()
    a, b = FakeWS(), FakeWS()
    mgr.connect(a)
    mgr.connect(b)
    mgr.disconnect(a)

    await mgr.broadcast({"x": 1})

    assert a.sent == []
    assert b.sent == ['{"x": 1}']


async def test_broadcast_drops_a_connection_that_errors():
    mgr = ConnectionManager()
    good, bad = FakeWS(), FakeWS(fail=True)
    mgr.connect(good)
    mgr.connect(bad)

    await mgr.broadcast({"x": 1})

    assert mgr.count == 1  # the failing connection was evicted
    assert good.sent == ['{"x": 1}']


async def test_broadcaster_pushes_predictions_from_the_bus_to_clients():
    bus = MemoryBus()
    mgr = ConnectionManager()
    ws = FakeWS()
    mgr.connect(ws)
    await bus.send(PREDICTIONS_OUT, "BTCUSDT", {"symbol": "BTCUSDT", "strategy_id": "momentum"})

    await broadcast_predictions(bus, mgr, max_records=1)

    assert len(ws.sent) == 1
    assert "momentum" in ws.sent[0]
    assert "prediction" in ws.sent[0]  # tagged with a message type


def test_health_and_symbols_routes():
    app = create_app(start_pipeline=False)  # no background tasks / network
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ok"
        body = client.get("/api/symbols").json()
        assert "BTCUSDT" in body["symbols"]
        assert body["strategies"] == ["momentum", "sentiment_llm", "ensemble", "deep_analysis"]

        index = client.get("/")  # dashboard (built React) or the inline fallback page
        assert index.status_code == 200
        assert "realtime-alpha" in index.text
