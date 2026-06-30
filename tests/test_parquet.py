import io

import polars as pl

from realtime_alpha.lakehouse.parquet import LocalWriter, R2Writer, rows_to_parquet


def test_rows_to_parquet_round_trips():
    rows = [
        {"symbol": "BTCUSDT", "yhat": 0.01, "hit": True},
        {"symbol": "ETHUSDT", "yhat": -0.02, "hit": False},
    ]
    df = pl.read_parquet(io.BytesIO(rows_to_parquet(rows)))
    assert df.to_dicts() == rows


def test_local_writer_writes_nested_key(tmp_path):
    LocalWriter(tmp_path).write("outcomes/dt=2026-06-29/symbol=BTCUSDT/part-1.parquet", b"hello")
    assert (tmp_path / "outcomes/dt=2026-06-29/symbol=BTCUSDT/part-1.parquet").read_bytes() == b"hello"


class _FakeS3:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def put_object(self, *, Bucket, Key, Body):  # noqa: N803 - boto3 kwarg names
        self.calls.append((Bucket, Key, Body))


def test_r2_writer_puts_object_with_injected_client():
    fake = _FakeS3()
    w = R2Writer(endpoint="https://x.r2", bucket="rta-lakehouse", access_key="k", secret_key="s", client=fake)
    w.write("outcomes/part-1.parquet", b"data")
    assert fake.calls == [("rta-lakehouse", "outcomes/part-1.parquet", b"data")]
