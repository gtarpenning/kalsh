from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence, TypeVar

from .client import KalshiClient
from . import schemas
from .storage import Market, RequestMetadata, Store, Trade

T = TypeVar("T")


class KalshiIngestor:
    def __init__(self, client: KalshiClient, store: Store, *, raw_source: str = "kalshi") -> None:
        self._client = client
        self._store = store
        self._raw_source = raw_source

    def ingest_markets(self, *, status: str | None = None, per_page: int | None = None) -> None:
        self._consume_pages(
            path=KalshiClient.MARKETS_PATH,
            params={"status": status, "per_page": per_page},
            source_suffix="markets",
            extract_key="markets",
            normalizer=self._normalize_market,
            writer=self._store.write_markets,
        )

    def ingest_trades(
        self,
        market_id: str,
        *,
        status: str | None = None,
        per_page: int | None = None,
    ) -> None:
        self._consume_pages(
            path=KalshiClient.TRADES_PATH,
            params={"market_id": market_id, "status": status, "per_page": per_page},
            source_suffix="trades",
            source_context=market_id,
            extract_key="trades",
            normalizer=self._make_trade_normalizer(market_id),
            writer=self._store.write_trades,
        )

    def _consume_pages(
        self,
        *,
        path: str,
        params: Mapping[str, Any | None],
        source_suffix: str,
        extract_key: str,
        normalizer: Callable[[Mapping[str, Any]], T],
        writer: Callable[[Sequence[T]], None],
        source_context: str | None = None,
    ) -> None:
        compacted_params = self._compact_params(params)
        source = self._render_source(source_suffix, source_context)
        context_market_id = source_context

        def log_request(method: str, path: str, request_params: Mapping[str, Any]) -> None:
            params_copy = dict(request_params or {})
            metadata = RequestMetadata(
                source=source,
                endpoint=path,
                method=method,
                params=params_copy,
                cursor=params_copy.get("cursor"),
                market_id=context_market_id or params_copy.get("market_id"),
            )
            self._store.write_request_metadata([metadata])

        for page in self._client.paginate(
            path, params=compacted_params, request_logger=log_request
        ):
            self._store.write_raw_payload(source, page)
            items = self._extract_items(page, extract_key)
            writer([normalizer(item) for item in items])

    @staticmethod
    def _compact_params(params: Mapping[str, Any | None]) -> Mapping[str, Any] | None:
        compacted = {key: value for key, value in params.items() if value is not None}
        return compacted or None

    @staticmethod
    def _extract_items(page: Mapping[str, Any], key: str) -> Sequence[Mapping[str, Any]]:
        value = page.get(key)
        if isinstance(value, (list, tuple)):
            return list(value)
        return []

    def _render_source(self, suffix: str, context: str | None) -> str:
        if context:
            return f"{self._raw_source}:{suffix}:{context}"
        return f"{self._raw_source}:{suffix}"

    def _make_trade_normalizer(self, market_id: str) -> Callable[[Mapping[str, Any]], Trade]:
        def normalize(payload: Mapping[str, Any]) -> Trade:
            return self._normalize_trade(payload, market_id)

        return normalize

    @staticmethod
    def _normalize_market(payload: Mapping[str, Any] | schemas.Market) -> Market:
        """Normalize Kalshi API market payload to internal Market format.
        
        Actual API field mapping (verified 2026-01-10):
            ticker -> market_id (primary identifier)
            title  -> name (market title/description)
        """
        if isinstance(payload, schemas.Market):
            return Market(
                market_id=payload.ticker,
                name=payload.title,
                status=payload.status,
                volume=float(payload.volume) if payload.volume is not None else None,
                liquidity=float(payload.liquidity) if payload.liquidity is not None else None,
                yes_bid=float(payload.yes_bid) if payload.yes_bid is not None else None,
                no_bid=float(payload.no_bid) if payload.no_bid is not None else None,
                yes_ask=float(payload.yes_ask) if payload.yes_ask is not None else None,
                no_ask=float(payload.no_ask) if payload.no_ask is not None else None,
                close_time=payload.close_time.isoformat() if payload.close_time else None,
                series_ticker=payload.series_ticker,
            )
        
        market_id = KalshiIngestor._pick_first(payload, "ticker", "market_id", "id")
        if market_id is None:
            raise ValueError("market payload missing ticker/market_id")
        name = KalshiIngestor._pick_first(payload, "title", "name", "event_name") or ""
        
        return Market(
            market_id=str(market_id),
            name=str(name),
            status=KalshiIngestor._pick_first(payload, "status"),
            volume=KalshiIngestor._safe_float(payload.get("volume")),
            liquidity=KalshiIngestor._safe_float(payload.get("liquidity")),
            yes_bid=KalshiIngestor._safe_float(payload.get("yes_bid")),
            no_bid=KalshiIngestor._safe_float(payload.get("no_bid")),
            yes_ask=KalshiIngestor._safe_float(payload.get("yes_ask")),
            no_ask=KalshiIngestor._safe_float(payload.get("no_ask")),
            close_time=KalshiIngestor._pick_first(payload, "close_time", "expiration_time"),
            series_ticker=KalshiIngestor._pick_first(payload, "series_ticker"),
        )
    
    @staticmethod
    def _safe_float(value: Any) -> float | None:
        """Safely convert value to float, return None if conversion fails."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _normalize_trade(payload: Mapping[str, Any] | schemas.Trade, fallback_market_id: str) -> Trade:
        """Normalize Kalshi API trade payload to internal Trade format.
        
        Actual API field mapping (verified 2026-01-10):
            trade_id      -> trade_id (UUID string)
            ticker        -> market_id (market identifier)
            count         -> quantity (number of contracts)
            created_time  -> timestamp (ISO string -> unix ms)
            price         -> price (decimal 0.0-1.0)
            user_id       -> NOT AVAILABLE (privacy - defaults to "anonymous")
        
        See order_chain.py for full field documentation.
        """
        from datetime import datetime
        
        if isinstance(payload, schemas.Trade):
            timestamp = int(payload.created_time.timestamp() * 1000)
            return Trade(
                trade_id=payload.trade_id,
                market_id=payload.ticker,
                user_id="anonymous",
                price=payload.price,
                quantity=float(payload.count),
                timestamp=timestamp,
            )
        
        trade_id = KalshiIngestor._pick_first(payload, "trade_id", "id")
        if trade_id is None:
            raise ValueError("trade payload missing trade_id")
        market_id = KalshiIngestor._pick_first(payload, "ticker", "market_id")
        if market_id is None:
            market_id = fallback_market_id
        user_id = KalshiIngestor._pick_first(payload, "user_id", "account_id", "member_id")
        if user_id is None:
            user_id = "anonymous"
        price = KalshiIngestor._pick_first(payload, "price", "rate")
        quantity = KalshiIngestor._pick_first(payload, "count", "quantity", "qty")
        timestamp_raw = KalshiIngestor._pick_first(payload, "created_time", "timestamp", "ts")
        if price is None or quantity is None or timestamp_raw is None:
            raise ValueError("trade payload missing price, quantity, or timestamp")
        
        if isinstance(timestamp_raw, str):
            timestamp = int(datetime.fromisoformat(timestamp_raw.replace("Z", "+00:00")).timestamp() * 1000)
        else:
            timestamp = int(timestamp_raw)
        
        return Trade(
            trade_id=str(trade_id),
            market_id=str(market_id),
            user_id=str(user_id),
            price=float(price),
            quantity=float(quantity),
            timestamp=timestamp,
        )

    @staticmethod
    def _pick_first(payload: Mapping[str, Any], *keys: str) -> Any | None:
        for key in keys:
            if key in payload and payload[key] is not None:
                return payload[key]
        return None

