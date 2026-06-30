from realtime_alpha.core import Outcome
from realtime_alpha.db.store import OUTCOME_COLS, outcome_to_row, row_to_outcome


def _o() -> Outcome:
    return Outcome("BTCUSDT", "momentum", 60, 0.001, 0.0008, True, 0.0002, 0.7, 100.0, 100.08, 1000, 61000, "v1")


def test_outcome_row_round_trips():
    o = _o()
    row = dict(zip(OUTCOME_COLS, outcome_to_row(o), strict=True))
    assert row_to_outcome(row) == o


def test_outcome_to_row_matches_columns():
    vals = outcome_to_row(_o())
    assert len(vals) == len(OUTCOME_COLS)
    assert vals[OUTCOME_COLS.index("strategy_id")] == "momentum"
    assert vals[OUTCOME_COLS.index("hit")] is True
    assert vals[OUTCOME_COLS.index("scored_ts")] == 61000
