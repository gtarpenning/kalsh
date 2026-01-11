import sqlite3

from kalsh.storage import SQLiteStore, Trade


def test_write_raw_payload_is_deduped(tmp_path):
    db_path = tmp_path / "storage.db"
    store = SQLiteStore(str(db_path))
    payload = {"symbol": "ABC", "price": 42}

    store.write_raw_payload("raw-source", payload)
    store.write_raw_payload("raw-source", payload)

    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM raw_payload").fetchone()[0]

    assert count == 1


def test_write_trades_upserts_by_trade_id(tmp_path):
    store = SQLiteStore(str(tmp_path / "storage.db"))
    original = Trade("trade-1", "market-1", "user-1", price=10.0, quantity=1.0, timestamp=100)
    updated = Trade("trade-1", "market-1", "user-1", price=12.5, quantity=2.0, timestamp=150)

    store.write_trades([original])
    store.write_trades([updated])

    stored = list(store.iter_trades("market-1", 0, 999))

    assert stored == [updated]


def test_iter_trades_filters_by_market_and_time_range(tmp_path):
    store = SQLiteStore(str(tmp_path / "storage.db"))
    trades = [
        Trade("trade-m1-early", "market-1", "user-1", price=1.0, quantity=1.0, timestamp=50),
        Trade("trade-m2", "market-2", "user-2", price=2.0, quantity=1.5, timestamp=120),
        Trade("trade-m1-keep", "market-1", "user-1", price=3.5, quantity=1.5, timestamp=200),
        Trade("trade-m1-late", "market-1", "user-1", price=4.7, quantity=2.0, timestamp=300),
        Trade("trade-m1-after", "market-1", "user-1", price=5.0, quantity=2.5, timestamp=400),
    ]

    store.write_trades(trades)

    results = list(store.iter_trades("market-1", 150, 350))

    assert [trade.trade_id for trade in results] == [
        "trade-m1-keep",
        "trade-m1-late",
    ]

