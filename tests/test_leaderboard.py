from realtime_alpha.core import Outcome
from realtime_alpha.evaluation import Leaderboard


def _out(strategy: str, hit: bool, conf: float = 0.6, err: float = 0.0) -> Outcome:
    return Outcome(
        symbol="BTCUSDT", strategy_id=strategy, horizon_s=60, yhat=0.01,
        realized_return=0.01 if hit else -0.01, hit=hit, abs_error=err, confidence=conf,
        ref_price=100.0, realized_price=101.0, pred_ts=1, scored_ts=2,
    )


def test_standings_ranked_by_directional_accuracy():
    lb = Leaderboard(min_samples=1)
    for _ in range(3):
        lb.add(_out("momentum", hit=True))
    lb.add(_out("momentum", hit=False))  # momentum 3/4 = 0.75
    for _ in range(2):
        lb.add(_out("ensemble", hit=True))
    lb.add(_out("ensemble", hit=False))
    lb.add(_out("ensemble", hit=False))  # ensemble 2/4 = 0.5

    s = lb.standings()
    assert [x.strategy_id for x in s] == ["momentum", "ensemble"]
    assert s[0].dir_acc == 0.75 and s[0].n == 4
    assert s[1].dir_acc == 0.5


def test_window_bounds_rolling_history():
    lb = Leaderboard(window=2, min_samples=1)
    lb.add(_out("m", hit=False))
    lb.add(_out("m", hit=True))
    lb.add(_out("m", hit=True))  # only the last 2 kept -> 2/2
    top = lb.standings()[0]
    assert top.dir_acc == 1.0 and top.n == 2


def test_degradation_alert_fires_once_below_floor():
    lb = Leaderboard(window=50, min_samples=4, degrade_floor=0.5)
    alerts = [lb.add(_out("bad", hit=False)) for _ in range(4)]  # 0% over 4 samples
    fired = [a for a in alerts if a is not None]
    assert len(fired) == 1
    assert fired[0].kind == "accuracy_degradation" and fired[0].severity == "warning"
    assert lb.add(_out("bad", hit=False)) is None  # still degraded -> no re-fire (hysteresis)


def test_no_alert_below_min_samples():
    lb = Leaderboard(min_samples=10, degrade_floor=0.9)
    alerts = [lb.add(_out("x", hit=False)) for _ in range(5)]
    assert all(a is None for a in alerts)


def test_seed_rebuilds_standings_from_outcomes():
    lb = Leaderboard(min_samples=1)
    lb.seed([_out("momentum", hit=True), _out("momentum", hit=False), _out("ensemble", hit=True)])
    by = {x.strategy_id: x for x in lb.standings()}
    assert by["momentum"].n == 2 and by["momentum"].dir_acc == 0.5
    assert by["ensemble"].dir_acc == 1.0
