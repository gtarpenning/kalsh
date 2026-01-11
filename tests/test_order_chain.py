from __future__ import annotations

import json
from pathlib import Path

from kalsh.order_chain import (
    ORDER_CHAIN_STEPS,
    evaluate_trade_field_coverage,
    missing_trade_fields,
)


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "order_chain"


def _load_fixture(name: str) -> dict[str, list[dict[str, object]]]:
    path = FIXTURE_DIR / name
    with path.open() as handle:
        return json.load(handle)


def test_chain_steps_document_filters_and_cursor_requirements() -> None:
    assert ORDER_CHAIN_STEPS[0].name == "list_markets"
    assert "per_page" in ORDER_CHAIN_STEPS[0].required_params
    assert "cursor" in ORDER_CHAIN_STEPS[0].required_params

    trades_step = ORDER_CHAIN_STEPS[1]
    assert trades_step.name == "list_trades"
    assert "market_id" in trades_step.required_params
    assert "cursor" in trades_step.required_params
    assert trades_step.recommended_filters["limit"] == 500


def test_trade_field_coverage_with_fixture_records_all_required_fields() -> None:
    """Test that fixture reflects actual API fields (verified 2026-01-10)."""
    trades = _load_fixture("list_trades_sample.json")["trades"]
    coverage = evaluate_trade_field_coverage(trades)

    available_fields = ["trade_id", "ticker", "price", "count", "created_time", "no_price", "yes_price", "taker_side"]
    for field in available_fields:
        assert coverage.get(field), f"{field} should be present in fixture (actual API field)"

    unavailable_fields = ["user_id", "account_id", "order_id"]
    for field in unavailable_fields:
        assert not coverage.get(field), f"{field} should NOT be in fixture (not in public API)"


def test_missing_trade_fields_reports_absent_fields() -> None:
    """Test missing_trade_fields utility with minimal payload."""
    trades = [
        {"trade_id": "t1", "ticker": "KXTEST"},
    ]
    missing = missing_trade_fields(trades)
    assert "price" in missing
    assert "count" in missing
    assert "created_time" in missing
