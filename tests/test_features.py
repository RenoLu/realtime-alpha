import pytest

from realtime_alpha.processor.features import FeatureEngine


def test_first_tick_seeds_emas_and_vwap_but_has_no_history_features():
    eng = FeatureEngine("BTCUSDT", ema_fast=2, ema_slow=4, rsi_period=3, vol_window=2)
    fw = eng.update(price=100.0, volume=1.0, ts=1)

    assert fw.symbol == "BTCUSDT" and fw.last_price == 100.0 and fw.ts == 1
    assert fw.features["ema_fast"] == 100.0
    assert fw.features["ema_slow"] == 100.0
    assert fw.features["vwap"] == 100.0
    # No return yet, so no return-derived features.
    assert "ret_1" not in fw.features
    assert "vol" not in fw.features
    assert "rsi" not in fw.features


def test_ema_fast_updates_incrementally_and_emits_ret_1():
    eng = FeatureEngine("BTCUSDT", ema_fast=2, ema_slow=4, rsi_period=3, vol_window=2)
    eng.update(100.0, 1.0, 1)  # seed at 100
    fw = eng.update(110.0, 1.0, 2)
    # alpha_fast = 2/(2+1) = 2/3  ->  2/3*110 + 1/3*100 = 106.6667
    assert fw.features["ema_fast"] == pytest.approx(106.6666667)
    assert fw.features["ret_1"] == pytest.approx(0.1)


def test_vwap_is_volume_weighted_across_ticks():
    eng = FeatureEngine("BTCUSDT", ema_fast=2, ema_slow=4, rsi_period=3, vol_window=2)
    eng.update(100.0, 2.0, 1)
    fw = eng.update(200.0, 3.0, 2)
    # (100*2 + 200*3) / (2+3) = 800 / 5 = 160
    assert fw.features["vwap"] == pytest.approx(160.0)


def test_rolling_vol_is_zero_when_returns_are_identical():
    eng = FeatureEngine("BTCUSDT", ema_fast=2, ema_slow=4, rsi_period=3, vol_window=2)
    eng.update(100.0, 1.0, 1)
    eng.update(110.0, 1.0, 2)  # ret +0.1, only one return so far
    fw = eng.update(121.0, 1.0, 3)  # ret +0.1, now two equal returns -> std 0
    assert fw.features["vol"] == pytest.approx(0.0, abs=1e-12)


def test_rsi_is_100_on_a_pure_uptrend_once_seeded():
    eng = FeatureEngine("BTCUSDT", ema_fast=2, ema_slow=4, rsi_period=3, vol_window=2)
    fw = None
    for price in (100.0, 110.0, 120.0, 130.0):  # 3 gains -> seeds at the 3rd delta
        fw = eng.update(price, 1.0, 1)
    assert fw.features["rsi"] == pytest.approx(100.0)


def test_rsi_absent_before_enough_deltas():
    eng = FeatureEngine("BTCUSDT", ema_fast=2, ema_slow=4, rsi_period=14, vol_window=2)
    eng.update(100.0, 1.0, 1)
    fw = eng.update(110.0, 1.0, 2)  # only one delta; rsi_period is 14
    assert "rsi" not in fw.features
