from realtime_alpha.core import FeatureWindow
from realtime_alpha.ml.dataset import DEFAULT_FEATURE_COLS, build_dataset, features_to_vector


def _w(price: float, ts: int, **feats: float) -> FeatureWindow:
    return FeatureWindow("BTCUSDT", ts, price, feats)


def _full(price: float, ts: int) -> FeatureWindow:
    return _w(price, ts, ema_fast=price, ema_slow=price, rsi=50.0, vol=0.001, ret_1=0.0, vwap=price)


def test_features_to_vector_orders_and_defaults_missing_to_zero():
    assert features_to_vector({"rsi": 60.0, "vol": 0.002}, ["ema_fast", "rsi", "vol"]) == [0.0, 60.0, 0.002]


def test_build_dataset_labels_forward_return_sign():
    ws = [_full(100, 1), _full(101, 2), _full(100, 3)]  # up then down
    X, y, cols = build_dataset(ws, horizon=1)
    assert cols == list(DEFAULT_FEATURE_COLS)
    assert len(X) == 2  # the last window has no forward label
    assert y == [1, 0]  # 100->101 up, 101->100 down
    assert X[0] == features_to_vector(ws[0].features, cols)


def test_build_dataset_drops_warmup_rows_missing_features():
    ws = [_w(100, 1, ema_fast=100.0), _full(101, 2), _full(102, 3)]  # first lacks most cols
    X, y, _ = build_dataset(ws, horizon=1)
    assert len(X) == 1 and y == [1]  # only the full, labelled window survives
