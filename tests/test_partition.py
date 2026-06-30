from realtime_alpha.bus import FEATURES_OUT, PREDICTIONS_OUT, SCORES_OUT, TRADES_RAW
from realtime_alpha.lakehouse.partition import Partition, partition_for


def test_partition_for_features_uses_ts_for_date():
    p = partition_for(FEATURES_OUT, {"symbol": "BTCUSDT", "ts": 0})  # 1970-01-01 UTC
    assert p == Partition(dataset="features", dt="1970-01-01", symbol="BTCUSDT")


def test_topic_maps_to_dataset():
    assert partition_for(PREDICTIONS_OUT, {"symbol": "ETHUSDT", "ts": 0}).dataset == "predictions"
    assert partition_for(SCORES_OUT, {"symbol": "ETHUSDT", "scored_ts": 0}).dataset == "outcomes"


def test_outcome_falls_back_to_scored_ts():
    # Outcome records carry scored_ts/pred_ts, not ts.
    p = partition_for(SCORES_OUT, {"symbol": "BTCUSDT", "scored_ts": 86_400_000})  # 1970-01-02
    assert p.dt == "1970-01-02" and p.symbol == "BTCUSDT"


def test_unknown_topic_is_not_persisted():
    assert partition_for(TRADES_RAW, {"symbol": "BTCUSDT", "ts": 0}) is None


def test_prefix_is_hive_partitioned():
    p = Partition(dataset="outcomes", dt="2026-06-29", symbol="BTCUSDT")
    assert p.prefix == "outcomes/dt=2026-06-29/symbol=BTCUSDT"
