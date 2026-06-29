import sys

import pytest

pytest.importorskip("yfinance")
pytest.importorskip("stockstats")


def test_vendored_dataflows_imports_without_langchain():
    # The connectors are vendored from TradingAgents but must stay isolated from its
    # LangGraph/LangChain agent stack.
    from realtime_alpha.dataflows import (  # noqa: F401
        config,
        interface,
        polymarket,
        reddit,
        stocktwits,
        yfinance_news,
    )

    assert "data_vendors" in config.get_config()
    loaded = [
        m for m in sys.modules if m.split(".")[0] in ("langchain", "langgraph", "langchain_core")
    ]
    assert loaded == [], f"vendored dataflows pulled in langchain: {loaded}"
