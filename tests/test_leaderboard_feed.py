import json

from realtime_alpha.bus import ALERTS_OUT, SCORES_OUT, MemoryBus
from realtime_alpha.core import Outcome
from realtime_alpha.evaluation import Leaderboard
from realtime_alpha.serving.leaderboard_feed import run_leaderboard_feed
from realtime_alpha.serving.ws_hub import ConnectionManager


class FakeWS:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_text(self, data: str) -> None:
        self.sent.append(data)


def _loss(strategy: str = "momentum") -> Outcome:
    return Outcome("BTCUSDT", strategy, 60, 0.01, -0.01, False, 0.02, 0.6, 100.0, 99.0, 1, 2)


async def test_feed_broadcasts_standings_and_degradation_alert():
    bus = MemoryBus()
    mgr = ConnectionManager()
    ws = FakeWS()
    mgr.connect(ws)
    lb = Leaderboard(min_samples=2, degrade_floor=0.6)

    for _ in range(2):  # two losses -> 0% acc over 2 samples -> degraded
        await bus.send(SCORES_OUT, "BTCUSDT", _loss().to_dict())

    await run_leaderboard_feed(bus, mgr, lb, max_records=2)

    msgs = [json.loads(m) for m in ws.sent]
    types = [m["type"] for m in msgs]
    assert "leaderboard" in types
    last_board = [m for m in msgs if m["type"] == "leaderboard"][-1]
    assert last_board["standings"][0]["strategy_id"] == "momentum"
    assert last_board["standings"][0]["n"] == 2

    alerts = [m for m in msgs if m["type"] == "alert"]
    assert len(alerts) == 1 and alerts[0]["kind"] == "accuracy_degradation"
    # the alert is also published to the bus for other consumers
    assert len(bus.history(ALERTS_OUT)) == 1
