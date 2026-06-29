from realtime_alpha.core import DeepView, FeatureWindow, PredictionContext
from realtime_alpha.deep import DeepViewCache
from realtime_alpha.strategies import registered_ids
from realtime_alpha.strategies.deep_analysis import DeepAnalysisStrategy


def _fw(ts: int = 1000, price: float = 100.0) -> FeatureWindow:
    return FeatureWindow("BTCUSDT", ts, price, {})


def _view() -> DeepView:
    return DeepView("BTCUSDT", "bullish", 0.012, 0.6, 3600, ts=500, briefing_md="...", model_ver="v1")


def test_deep_view_cache_set_get_snapshot():
    c = DeepViewCache()
    assert c.get("BTCUSDT") is None
    v = _view()
    c.set(v)
    assert c.get("BTCUSDT") is v
    assert c.snapshot() == {"BTCUSDT": v}


def test_deep_analysis_emits_standing_view_restamped_to_window():
    ctx = PredictionContext(deep={"BTCUSDT": _view()})
    p = DeepAnalysisStrategy().predict(_fw(ts=2000), ctx)
    assert p is not None
    assert p.strategy_id == "deep_analysis"
    assert p.yhat == 0.012 and p.confidence == 0.6 and p.horizon_s == 3600
    assert p.ts == 2000 and p.ref_price == 100.0 and p.model_ver == "v1"


def test_deep_analysis_none_without_view():
    assert DeepAnalysisStrategy().predict(_fw(), PredictionContext()) is None
    assert DeepAnalysisStrategy().predict(_fw(), None) is None


def test_deep_analysis_is_registered():
    assert "deep_analysis" in registered_ids()
