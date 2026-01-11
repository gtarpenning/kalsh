from __future__ import annotations

import sqlite3
import json
from unittest.mock import Mock

from kalsh.client import KalshiClient
from kalsh.ingestion import KalshiIngestor
from kalsh.storage import SQLiteStore


def test_raw_payloads_are_deduped(tmp_path):
    db_path = tmp_path / "storage.db"
    store = SQLiteStore(str(db_path))
    client = Mock(spec=KalshiClient)
    page = {"markets": [{"market_id": "market-1", "name": "Market One"}]}
    client.paginate.return_value = iter([page, page])

    KalshiIngestor(client, store).ingest_markets()

    with sqlite3.connect(str(db_path)) as conn:
        count = conn.execute("SELECT COUNT(*) FROM raw_payload").fetchone()[0]

    assert count == 1


def test_normalized_trades_are_available(tmp_path):
    db_path = tmp_path / "storage.db"
    store = SQLiteStore(str(db_path))
    trades_page = {
        "trades": [
            {
                "trade_id": "trade-1",
                "user_id": "user-1",
                "price": 10.5,
                "quantity": 3,
                "timestamp": 100,
            },
            {
                "trade_id": "trade-2",
                "user_id": "user-2",
                "price": 11.25,
                "quantity": 2,
                "timestamp": 150,
            },
        ]
    }
    client = Mock(spec=KalshiClient)
    client.paginate.return_value = iter([trades_page])

    KalshiIngestor(client, store).ingest_trades("market-1")

    stored = list(store.iter_trades("market-1", 0, 999))

    assert len(stored) == 2
    assert stored[0].trade_id == "trade-1"
    assert stored[0].market_id == "market-1"
    assert stored[1].trade_id == "trade-2"
    assert stored[1].market_id == "market-1"


def test_all_paginated_trade_pages_are_recorded(tmp_path):
    db_path = tmp_path / "storage.db"
    store = SQLiteStore(str(db_path))
    page_one = {
        "trades": [
            {
                "trade_id": "trade-a",
                "user_id": "user-a",
                "price": 1.5,
                "quantity": 1,
                "timestamp": 5,
            }
        ]
    }
    page_two = {
        "trades": [
            {
                "trade_id": "trade-b",
                "user_id": "user-b",
                "price": 2.5,
                "quantity": 2,
                "timestamp": 10,
            }
        ]
    }

    def mock_paginate(path, params=None, request_logger=None):
        assert path == KalshiClient.TRADES_PATH
        assert params == {"market_id": "page-market", "per_page": 5}
        if request_logger:
            request_logger("GET", path, dict(params or {}))
        return iter([page_one, page_two])

    client = Mock(spec=KalshiClient)
    client.paginate.side_effect = mock_paginate

    KalshiIngestor(client, store).ingest_trades("page-market", per_page=5)

    with sqlite3.connect(str(db_path)) as conn:
        raw_count = conn.execute("SELECT COUNT(*) FROM raw_payload").fetchone()[0]

    assert raw_count == 2
    assert [trade.trade_id for trade in store.iter_trades("page-market", 0, 999)] == [
        "trade-a",
        "trade-b",
    ]
    assert client.paginate.call_count == 1


def test_ingestor_records_market_request_metadata(tmp_path):
    db_path = tmp_path / "storage.db"
    store = SQLiteStore(str(db_path))
    client = Mock(spec=KalshiClient)
    page = {
        "markets": [
            {"market_id": "market-1", "name": "Market One"},
        ],
    }
    def mock_paginate(path, params=None, request_logger=None):
        if request_logger:
            request_logger("GET", path, dict(params or {}))
        return iter([page])

    client.paginate.side_effect = mock_paginate

    KalshiIngestor(client, store).ingest_markets(per_page=5)

    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute(
            "SELECT endpoint, params, cursor FROM request_metadata"
        ).fetchone()

    assert row[0] == KalshiClient.MARKETS_PATH
    params = json.loads(row[1])
    assert params.get("per_page") == 5
    assert row[2] is None


def test_ingestor_records_trade_metadata_with_market_context(tmp_path):
    db_path = tmp_path / "storage.db"
    store = SQLiteStore(str(db_path))
    client = Mock(spec=KalshiClient)
    trades_page = {
        "trades": [
            {
                "trade_id": "trade-1",
                "market_id": "market-foo",
                "user_id": "user-foo",
                "price": 1.0,
                "quantity": 2.0,
                "timestamp": 123,
            }
        ]
    }
    def mock_paginate(path, params=None, request_logger=None):
        if request_logger:
            request_logger("GET", path, dict(params or {}))
        return iter([trades_page])

    client.paginate.side_effect = mock_paginate

    KalshiIngestor(client, store).ingest_trades("market-foo", per_page=3)

    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute(
            "SELECT endpoint, params, market_id FROM request_metadata"
        ).fetchone()

    assert row[0] == KalshiClient.TRADES_PATH
    params = json.loads(row[1])
    assert params.get("market_id") == "market-foo"
    assert row[2] == "market-foo"

