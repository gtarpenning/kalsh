"""SQLite-backed store for Kalshi data with basic interfaces."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Iterator, Mapping, Sequence, Protocol, Union

Payload = Union[str, Mapping[str, Any], Sequence[Any]]


@dataclass(frozen=True)
class Market:
    """Minimal metadata captured about a market."""

    market_id: str
    name: str
    status: str | None = None
    volume: float | None = None
    liquidity: float | None = None
    yes_bid: float | None = None
    no_bid: float | None = None
    yes_ask: float | None = None
    no_ask: float | None = None
    close_time: str | None = None
    series_ticker: str | None = None
    last_fetched: int | None = None


@dataclass(frozen=True)
class Trade:
    """Normalized representation of a Kalshi trade."""

    trade_id: str
    market_id: str
    user_id: str
    price: float
    quantity: float
    timestamp: int


@dataclass(frozen=True)
class RequestMetadata:
    """Readable record describing each API request that produced a raw payload."""

    source: str
    endpoint: str
    method: str
    params: Mapping[str, Any]
    cursor: str | None
    market_id: str | None
    received_at: int | None = None


class Store(Protocol):
    """Store contract used for persistence testing."""

    def write_raw_payload(
        self, source: str, payload: Payload, *, received_at: int | None = None
    ) -> None:
        raise NotImplementedError

    def write_markets(self, markets: Sequence[Market]) -> None:
        raise NotImplementedError

    def write_trades(self, trades: Sequence[Trade]) -> None:
        raise NotImplementedError

    def iter_trades(self, market_id: str, start_ts: int, end_ts: int) -> Iterator[Trade]:
        raise NotImplementedError

    def write_request_metadata(self, records: Sequence[RequestMetadata]) -> None:
        raise NotImplementedError


class SQLiteStore:
    """SQLite implementation of the storage interface."""

    def __init__(self, db_path: str) -> None:
        self._conn = sqlite3.connect(db_path, isolation_level=None, check_same_thread=False)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS raw_payload (
                source TEXT NOT NULL,
                payload TEXT NOT NULL,
                received_at INTEGER NOT NULL,
                PRIMARY KEY (source, payload)
            );

            CREATE TABLE IF NOT EXISTS markets (
                market_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                status TEXT,
                volume REAL,
                liquidity REAL,
                yes_bid REAL,
                no_bid REAL,
                yes_ask REAL,
                no_ask REAL,
                close_time TEXT,
                series_ticker TEXT,
                last_fetched INTEGER
            );

            CREATE TABLE IF NOT EXISTS trades (
                trade_id TEXT PRIMARY KEY,
                market_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                price REAL NOT NULL,
                quantity REAL NOT NULL,
                timestamp INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS request_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                method TEXT NOT NULL,
                params TEXT NOT NULL,
                cursor TEXT,
                market_id TEXT,
                received_at INTEGER NOT NULL
            );
            """
        )
        self._migrate_schema()
        self._create_indexes()

    def _migrate_schema(self) -> None:
        """Apply migrations to handle schema changes in existing databases."""
        cursor = self._conn.execute("PRAGMA table_info(markets)")
        columns = {row[1] for row in cursor.fetchall()}
        
        new_columns = [
            ("status", "TEXT"),
            ("volume", "REAL"),
            ("liquidity", "REAL"),
            ("yes_bid", "REAL"),
            ("no_bid", "REAL"),
            ("yes_ask", "REAL"),
            ("no_ask", "REAL"),
            ("close_time", "TEXT"),
            ("series_ticker", "TEXT"),
            ("last_fetched", "INTEGER"),
        ]
        
        for column_name, column_type in new_columns:
            if column_name not in columns:
                self._conn.execute(f"ALTER TABLE markets ADD COLUMN {column_name} {column_type}")

    def _create_indexes(self) -> None:
        """Create indexes for common queries."""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_markets_volume ON markets(volume DESC)",
            "CREATE INDEX IF NOT EXISTS idx_markets_liquidity ON markets(liquidity DESC)",
            "CREATE INDEX IF NOT EXISTS idx_markets_status ON markets(status)",
            "CREATE INDEX IF NOT EXISTS idx_markets_last_fetched ON markets(last_fetched)",
        ]
        for index_sql in indexes:
            self._conn.execute(index_sql)

    def write_raw_payload(
        self, source: str, payload: Payload, *, received_at: int | None = None
    ) -> None:
        payload_text = self._serialize_payload(payload)
        if received_at is None:
            received_at = int(time.time())
        with self._conn:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO raw_payload (source, payload, received_at)
                VALUES (?, ?, ?)
                """,
                (source, payload_text, received_at),
            )

    def write_markets(self, markets: Sequence[Market]) -> None:
        if not markets:
            return
        current_time = int(time.time())
        with self._conn:
            for market in markets:
                last_fetched = market.last_fetched if market.last_fetched is not None else current_time
                self._conn.execute(
                    """
                    INSERT INTO markets (
                        market_id, name, status, volume, liquidity,
                        yes_bid, no_bid, yes_ask, no_ask, close_time, series_ticker, last_fetched
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(market_id) DO UPDATE SET
                        name=excluded.name,
                        status=excluded.status,
                        volume=excluded.volume,
                        liquidity=excluded.liquidity,
                        yes_bid=excluded.yes_bid,
                        no_bid=excluded.no_bid,
                        yes_ask=excluded.yes_ask,
                        no_ask=excluded.no_ask,
                        close_time=excluded.close_time,
                        series_ticker=excluded.series_ticker,
                        last_fetched=excluded.last_fetched
                    """,
                    (
                        market.market_id,
                        market.name,
                        market.status,
                        market.volume,
                        market.liquidity,
                        market.yes_bid,
                        market.no_bid,
                        market.yes_ask,
                        market.no_ask,
                        market.close_time,
                        market.series_ticker,
                        last_fetched,
                    ),
                )

    def write_trades(self, trades: Sequence[Trade]) -> None:
        if not trades:
            return
        with self._conn:
            for trade in trades:
                self._conn.execute(
                    """
                    INSERT INTO trades (trade_id, market_id, user_id, price, quantity, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(trade_id) DO UPDATE SET
                        market_id=excluded.market_id,
                        user_id=excluded.user_id,
                        price=excluded.price,
                        quantity=excluded.quantity,
                        timestamp=excluded.timestamp
                    """,
                    (
                        trade.trade_id,
                        trade.market_id,
                        trade.user_id,
                        trade.price,
                        trade.quantity,
                        trade.timestamp,
                    ),
                )

    def iter_trades(self, market_id: str, start_ts: int, end_ts: int) -> Iterator[Trade]:
        cursor = self._conn.execute(
            """
            SELECT trade_id, market_id, user_id, price, quantity, timestamp
            FROM trades
            WHERE market_id = ? AND timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp ASC
            """,
            (market_id, start_ts, end_ts),
        )
        for trade_id, market_id, user_id, price, quantity, timestamp in cursor:
            yield Trade(
                trade_id=trade_id,
                market_id=market_id,
                user_id=user_id,
                price=price,
                quantity=quantity,
                timestamp=timestamp,
            )

    def _serialize_payload(self, payload: Payload) -> str:
        if isinstance(payload, str):
            return payload
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def write_request_metadata(self, records: Sequence[RequestMetadata]) -> None:
        if not records:
            return
        with self._conn:
            for record in records:
                params_text = self._serialize_payload(record.params)
                received_at = record.received_at or int(time.time())
                self._conn.execute(
                    """
                    INSERT INTO request_metadata
                        (source, endpoint, method, params, cursor, market_id, received_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.source,
                        record.endpoint,
                        record.method,
                        params_text,
                        record.cursor,
                        record.market_id,
                        received_at,
                    ),
                )
