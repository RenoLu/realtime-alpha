import pytest

from realtime_alpha.core import FeatureWindow
from realtime_alpha.strategies import (
    enabled_strategies,
    get_strategy,
    registered_ids,
)
from realtime_alpha.strategies.momentum import MomentumStrategy


def _fw(ema_fast: float, ema_slow: float, price: float = 100.0, ts: int = 1000) -> FeatureWindow:
    return FeatureWindow("BTCUSDT", ts, price, {"ema_fast": ema_fast, "ema_slow": ema_slow})


def test_momentum_predicts_up_when_fast_above_slow():
    p = MomentumStrategy(horizon_s=60).predict(_fw(101.0, 100.0))
    assert p is not None
    assert p.direction == 1
    assert p.strategy_id == "momentum"
    assert p.horizon_s == 60
    assert p.ts == 1000
    assert 0.0 <= p.confidence <= 1.0


def test_momentum_predicts_down_when_fast_below_slow():
    p = MomentumStrategy().predict(_fw(99.0, 100.0))
    assert p is not None
    assert p.direction == -1


def test_momentum_returns_none_without_required_features():
    assert MomentumStrategy().predict(FeatureWindow("BTCUSDT", 1, 100.0, {})) is None


def test_registry_lists_built_in_strategies():
    assert "momentum" in registered_ids()


def test_get_strategy_returns_instance_with_matching_id():
    assert get_strategy("momentum").id == "momentum"


def test_enabled_strategies_filters_by_config_ids():
    assert [s.id for s in enabled_strategies(["momentum"])] == ["momentum"]


def test_get_unknown_strategy_raises_keyerror():
    with pytest.raises(KeyError):
        get_strategy("does_not_exist")
