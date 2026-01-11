"""Describe the Kalshi market/trade chain and surface required payload fields."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from .client import KalshiClient


@dataclass(frozen=True)
class OrderChainStep:
    name: str
    method: str
    path: str
    description: str
    required_params: Sequence[str]
    recommended_filters: Mapping[str, Any]


ORDER_CHAIN_STEPS: Sequence[OrderChainStep] = (
    OrderChainStep(
        name="list_markets",
        method="GET",
        path=KalshiClient.MARKETS_PATH,
        description="Seed the market list using the same filters shown in the UI.",
        required_params=("status", "per_page", "cursor"),
        recommended_filters={"status": "open", "per_page": 100},
    ),
    OrderChainStep(
        name="list_trades",
        method="GET",
        path=KalshiClient.TRADES_PATH,
        description=(
            "Walk the paginated trade tape per market, tracking cursors + "
            "filters that reproduce the UI’s “order chain.”"
        ),
        required_params=("market_id", "limit", "cursor", "min_ts", "max_ts", "status"),
        recommended_filters={"limit": 500, "status": "filled"},
    ),
)

TRADE_FIELD_REQUIREMENTS: Sequence[str] = (
    "trade_id",
    "ticker",
    "user_id",
    "account_id",
    "order_id",
    "taker_side",
    "price",
    "count",
    "created_time",
    "no_price",
    "yes_price",
)

FIELD_DESCRIPTIONS: Mapping[str, str] = {
    "trade_id": "Stable identifier for the executed trade (UUID).",
    "ticker": "Market ticker identifier (used instead of market_id in trades).",
    "user_id": "Account identifier to attribute behavior (NOT AVAILABLE in public API).",
    "account_id": "Alternate account key (NOT AVAILABLE in public API).",
    "order_id": "Original order the trade fulfilled (NOT AVAILABLE in public API).",
    "taker_side": "Direction of the taker side: 'yes' or 'no'.",
    "price": "Execution price as decimal (0.0-1.0), e.g. 0.57 for 57 cents.",
    "count": "Number of contracts traded (use this, not 'quantity').",
    "created_time": "ISO 8601 timestamp string, e.g. '2026-01-10T02:06:47.991525Z'.",
    "no_price": "Integer price in cents for the 'no' side (e.g. 43 = $0.43).",
    "yes_price": "Integer price in cents for the 'yes' side (e.g. 57 = $0.57).",
}

ACTUAL_TO_NORMALIZED_MAPPING: Mapping[str, str] = {
    "trade_id": "trade_id",
    "ticker": "market_id",
    "count": "quantity",
    "created_time": "timestamp",
    "price": "price",
}

METADATA_STRATEGY = (
    "Persist every request emitted during pagination (endpoint, params, cursor, "
    "market_id, received timestamp) in `request_metadata` so detection runs can "
    "replay the exact same chain and surface confidence metrics."
)


def evaluate_trade_field_coverage(
    trades: Iterable[Mapping[str, Any]]
) -> Mapping[str, bool]:
    """Return which required trade fields are present in at least one payload."""

    coverage = {field: False for field in TRADE_FIELD_REQUIREMENTS}
    for trade in trades:
        for field in coverage:
            if coverage[field]:
                continue
            if field in trade and trade[field] is not None:
                coverage[field] = True
        if all(coverage.values()):
            break
    return coverage


def missing_trade_fields(trades: Iterable[Mapping[str, Any]]) -> Sequence[str]:
    """List trade fields that have never appeared in the provided payloads."""

    coverage = evaluate_trade_field_coverage(trades)
    return [field for field, seen in coverage.items() if not seen]
