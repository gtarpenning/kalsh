from __future__ import annotations

import sqlite3
from unittest.mock import Mock

from kalsh.client import KalshiClient
from kalsh.ingestion import KalshiIngestor
from kalsh.storage import SQLiteStore, Trade


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
                "price": 10.5,
                "quantity": 3,
                "timestamp": 100,
            },
            {
                "trade_id": "trade-2",
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

    assert stored == [
        Trade("trade-1", "market-1", price=10.5, quantity=3.0, timestamp=100),
        Trade("trade-2", "market-1", price=11.25, quantity=2.0, timestamp=150),
    ]


def test_all_paginated_trade_pages_are_recorded(tmp_path):
    db_path = tmp_path / "storage.db"
    store = SQLiteStore(str(db_path))
    page_one = {
        "trades": [
            {
                "trade_id": "trade-a",
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
                "price": 2.5,
                "quantity": 2,
                "timestamp": 10,
            }
        ]
    }

    def mock_paginate(path, params=None):
        assert path == KalshiClient.TRADES_PATH
        assert params == {"market_id": "page-market", "per_page": 5}
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

