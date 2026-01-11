"""Tests for the anomaly detection pipeline."""

from __future__ import annotations

from unittest.mock import Mock

from kalsh import schemas, storage
from kalsh.client import KalshiClient
from kalsh.pipeline import (
    DetectionCase,
    PipelineConfig,
    PipelineReporter,
    PipelineRunner,
    storage_trade_to_rule_trade,
)


def test_storage_trade_to_rule_trade_conversion():
    """Test conversion from storage.Trade to rules.Trade."""
    storage_trade = storage.Trade(
        trade_id="trade-123",
        market_id="market-abc",
        user_id="user-xyz",
        price=12.5,
        quantity=10.5,
        timestamp=1234567890,
    )

    rule_trade = storage_trade_to_rule_trade(storage_trade)

    assert rule_trade.market_id == "market-abc"
    assert rule_trade.user_id == "user-xyz"
    assert rule_trade.quantity == 10


def test_pipeline_runner_integration_with_mock_data(tmp_path):
    """Test pipeline runner with mocked client and store."""
    db_path = tmp_path / "pipeline_test.db"
    store = storage.SQLiteStore(str(db_path))

    markets_response = schemas.MarketsResponse(
        markets=[
            schemas.Market(ticker="market-1", title="Market One", status="open"),
            schemas.Market(ticker="market-2", title="Market Two", status="open"),
        ]
    )

    trades_response_1 = {
        "trades": [
            {
                "trade_id": f"trade-1-{i}",
                "market_id": "market-1",
                "user_id": "dominant-user",
                "price": 10.0,
                "quantity": 10,
                "timestamp": 1000 + i,
            }
            for i in range(5)
        ]
        + [
            {
                "trade_id": f"trade-1-small-{i}",
                "market_id": "market-1",
                "user_id": "small-user",
                "price": 10.0,
                "quantity": 1,
                "timestamp": 2000 + i,
            }
            for i in range(5)
        ]
    }

    trades_response_2 = {
        "trades": [
            {
                "trade_id": f"trade-2-{i}",
                "market_id": "market-2",
                "user_id": f"user-{i}",
                "price": 5.0,
                "quantity": 2,
                "timestamp": 3000 + i,
            }
            for i in range(3)
        ]
    }

    def mock_paginate(path, params=None, request_logger=None):
        if "trades" in path:
            market_id = params.get("market_id") if params else None
            if market_id == "market-1":
                if request_logger:
                    request_logger("GET", path, dict(params or {}))
                return iter([trades_response_1])
            elif market_id == "market-2":
                if request_logger:
                    request_logger("GET", path, dict(params or {}))
                return iter([trades_response_2])
        return iter([])

    client = Mock(spec=KalshiClient)
    client.list_markets.return_value = markets_response
    client.paginate.side_effect = mock_paginate

    config = PipelineConfig(
        market_limit=2, window_size=5, dominance_threshold=0.75
    )
    runner = PipelineRunner(client, store, config)

    cases = runner.run(market_status="open", dry_run=False)

    assert len(cases) > 0
    dominance_cases = [c for c in cases if c.rule == "dominance"]
    assert len(dominance_cases) > 0

    dominant_case = dominance_cases[0]
    assert dominant_case.market_id == "market-1"
    assert dominant_case.user_id == "dominant-user"


def test_pipeline_reporter_displays_cases():
    """Test that reporter formats and displays cases."""
    cases = [
        DetectionCase(
            market_id="market-abc",
            user_id="user-123",
            window_id=0,
            rule="dominance",
            reason={"rule": "dominance", "share": (3, 4), "window_id": 0},
        ),
        DetectionCase(
            market_id="market-xyz",
            user_id="user-456",
            window_id=1,
            rule="sudden_growth",
            reason={"rule": "sudden_growth", "growth": 5, "window_id": 1},
        ),
    ]

    reporter = PipelineReporter()
    reporter.report_cases(cases)


def test_pipeline_runner_handles_empty_markets(tmp_path):
    """Test pipeline handles no markets gracefully."""
    db_path = tmp_path / "empty_pipeline.db"
    store = storage.SQLiteStore(str(db_path))

    client = Mock(spec=KalshiClient)
    client.list_markets.return_value = schemas.MarketsResponse(markets=[])
    client.paginate.return_value = iter([])

    runner = PipelineRunner(client, store)
    cases = runner.run(market_status="open", dry_run=False)

    assert cases == []


def test_pipeline_runner_skips_markets_with_insufficient_trades(tmp_path):
    """Test that markets with fewer trades than window size are skipped."""
    db_path = tmp_path / "insufficient_trades.db"
    store = storage.SQLiteStore(str(db_path))

    markets_response = schemas.MarketsResponse(
        markets=[
            schemas.Market(ticker="market-small", title="Small Market", status="open")
        ]
    )

    trades_response = {
        "trades": [
            {
                "trade_id": "trade-1",
                "market_id": "market-small",
                "user_id": "user-1",
                "price": 10.0,
                "quantity": 5,
                "timestamp": 1000,
            }
        ]
    }

    def mock_paginate(path, params=None, request_logger=None):
        if request_logger:
            request_logger("GET", path, dict(params or {}))
        return iter([trades_response])

    client = Mock(spec=KalshiClient)
    client.list_markets.return_value = markets_response
    client.paginate.side_effect = mock_paginate

    config = PipelineConfig(window_size=10)
    runner = PipelineRunner(client, store, config)

    cases = runner.run(market_status="open", dry_run=False)

    assert cases == []


def test_reporter_sorts_by_rule():
    """Test reporter can sort cases by rule."""
    cases = [
        DetectionCase(
            market_id="market-b",
            user_id="user-1",
            window_id=0,
            rule="sudden_growth",
            reason={"rule": "sudden_growth", "growth": 5, "window_id": 0},
        ),
        DetectionCase(
            market_id="market-a",
            user_id="user-2",
            window_id=1,
            rule="dominance",
            reason={"rule": "dominance", "share": (3, 4), "window_id": 1},
        ),
    ]

    reporter = PipelineReporter()
    reporter.report_cases(cases, sort_by="rule")
