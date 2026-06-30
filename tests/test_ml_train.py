from realtime_alpha.ml.train import fetch_klines, fold_bounds, windows_from_klines


class _FakeResp:
    def __init__(self, data):
        self._d = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._d


class _FakeHttp:
    def __init__(self, data):
        self._d = data
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append(params)
        return _FakeResp(self._d)


def _kline(close, vol, close_time):
    # Binance kline: [openTime, open, high, low, close, volume, closeTime, ...]
    return [0, "0", "0", "0", str(close), str(vol), close_time, "0", "0", "0", "0", "0"]


def test_fetch_klines_parses_close_volume_and_closetime():
    http = _FakeHttp([_kline(100.0, 1.5, 1000), _kline(101.0, 2.0, 2000)])
    out = fetch_klines("BTCUSDT", interval="1m", limit=2, client=http)
    assert out == [(1000, 100.0, 1.5), (2000, 101.0, 2.0)]
    assert http.calls[0]["symbol"] == "BTCUSDT" and http.calls[0]["interval"] == "1m"


def test_windows_from_klines_drives_feature_engine():
    klines = [(i * 1000, 100.0 + i, 1.0) for i in range(40)]
    ws = windows_from_klines("BTCUSDT", klines)
    assert len(ws) == 40
    assert "rsi" in ws[-1].features  # warmed up by the end of the series


def test_fold_bounds_expanding_window():
    assert list(fold_bounds(100, n_splits=4)) == [(20, 40), (40, 60), (60, 80), (80, 100)]
