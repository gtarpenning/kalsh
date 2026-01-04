from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence, TypeVar

from .client import KalshiClient
from .storage import Market, Store, Trade

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
        for page in self._client.paginate(path, params=compacted_params):
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
    def _normalize_market(payload: Mapping[str, Any]) -> Market:
        market_id = KalshiIngestor._pick_first(payload, "market_id", "id")
        if market_id is None:
            raise ValueError("market payload missing market_id")
        name = KalshiIngestor._pick_first(payload, "name", "title", "event_name") or ""
        return Market(market_id=str(market_id), name=str(name))

    @staticmethod
    def _normalize_trade(payload: Mapping[str, Any], fallback_market_id: str) -> Trade:
        trade_id = KalshiIngestor._pick_first(payload, "trade_id", "id")
        if trade_id is None:
            raise ValueError("trade payload missing trade_id")
        market_id = KalshiIngestor._pick_first(payload, "market_id")
        if market_id is None:
            market_id = fallback_market_id
        price = KalshiIngestor._pick_first(payload, "price", "rate")
        quantity = KalshiIngestor._pick_first(payload, "quantity", "qty")
        timestamp = KalshiIngestor._pick_first(payload, "timestamp", "ts")
        if price is None or quantity is None or timestamp is None:
            raise ValueError("trade payload missing price, quantity, or timestamp")
        return Trade(
            trade_id=str(trade_id),
            market_id=str(market_id),
            price=float(price),
            quantity=float(quantity),
            timestamp=int(timestamp),
        )

    @staticmethod
    def _pick_first(payload: Mapping[str, Any], *keys: str) -> Any | None:
        for key in keys:
            if key in payload and payload[key] is not None:
                return payload[key]
        return None

