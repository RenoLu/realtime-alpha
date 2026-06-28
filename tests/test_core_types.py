from realtime_alpha.core import Alert, FeatureWindow, Prediction, Tick


def test_prediction_direction_is_sign_of_yhat():
    assert Prediction("BTCUSDT", 60, 0.001, 0.7, "momentum", ts=1000).direction == 1
    assert Prediction("BTCUSDT", 60, -0.001, 0.7, "momentum", ts=1000).direction == -1
    assert Prediction("BTCUSDT", 60, 0.0, 0.5, "momentum", ts=1000).direction == 0


def test_prediction_target_ts_adds_horizon_in_ms():
    p = Prediction("BTCUSDT", horizon_s=60, yhat=0.001, confidence=0.7, strategy_id="m", ts=10_000)
    assert p.target_ts == 10_000 + 60_000


def test_from_dict_ignores_unknown_keys():
    # A newer producer may add fields an older consumer doesn't know about.
    p = Prediction.from_dict(
        {
            "symbol": "ETHUSDT",
            "horizon_s": 30,
            "yhat": -0.002,
            "confidence": 0.4,
            "strategy_id": "logistic",
            "ts": 5,
            "model_ver": "v3",
            "some_future_field": "ignored",
        }
    )
    assert p.symbol == "ETHUSDT" and p.model_ver == "v3"


def test_round_trip_preserves_all_types():
    tick = Tick("BTCUSDT", 65000.5, 0.25, 1700)
    fw = FeatureWindow("BTCUSDT", 1700, 65000.5, {"ema_fast": 1.0, "rsi": 55.0})
    pred = Prediction("BTCUSDT", 60, 0.001, 0.7, "momentum", ts=1700, model_ver="v1")
    alert = Alert("BTCUSDT", "stale_feed", "warning", "no ticks for 30s", 1700)

    assert Tick.from_dict(tick.to_dict()) == tick
    assert FeatureWindow.from_dict(fw.to_dict()) == fw
    assert Prediction.from_dict(pred.to_dict()) == pred
    assert Alert.from_dict(alert.to_dict()) == alert
