"""SQLite-backed store for Kalshi data with basic interfaces."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Iterable, Iterator, Mapping, Sequence, Protocol, Union

Payload = Union[str, Mapping[str, Any], Sequence[Any]]


@dataclass(frozen=True)
class Market:
    """Minimal metadata captured about a market."""

    market_id: str
    name: str


@dataclass(frozen=True)
class Trade:
    """Normalized representation of a Kalshi trade."""

    trade_id: str
    market_id: str
    price: float
    quantity: float
    timestamp: int


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
                name TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS trades (
                trade_id TEXT PRIMARY KEY,
                market_id TEXT NOT NULL,
                price REAL NOT NULL,
                quantity REAL NOT NULL,
                timestamp INTEGER NOT NULL
            );
            """
        )

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
        with self._conn:
            for market in markets:
                self._conn.execute(
                    """
                    INSERT INTO markets (market_id, name)
                    VALUES (?, ?)
                    ON CONFLICT(market_id) DO UPDATE SET name=excluded.name
                    """,
                    (market.market_id, market.name),
                )

    def write_trades(self, trades: Sequence[Trade]) -> None:
        if not trades:
            return
        with self._conn:
            for trade in trades:
                self._conn.execute(
                    """
                    INSERT INTO trades (trade_id, market_id, price, quantity, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(trade_id) DO UPDATE SET
                        market_id=excluded.market_id,
                        price=excluded.price,
                        quantity=excluded.quantity,
                        timestamp=excluded.timestamp
                    """,
                    (
                        trade.trade_id,
                        trade.market_id,
                        trade.price,
                        trade.quantity,
                        trade.timestamp,
                    ),
                )

    def iter_trades(self, market_id: str, start_ts: int, end_ts: int) -> Iterator[Trade]:
        cursor = self._conn.execute(
            """
            SELECT trade_id, market_id, price, quantity, timestamp
            FROM trades
            WHERE market_id = ? AND timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp ASC
            """,
            (market_id, start_ts, end_ts),
        )
        for trade_id, market_id, price, quantity, timestamp in cursor:
            yield Trade(
                trade_id=trade_id,
                market_id=market_id,
                price=price,
                quantity=quantity,
                timestamp=timestamp,
            )

    def _serialize_payload(self, payload: Payload) -> str:
        if isinstance(payload, str):
            return payload
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

