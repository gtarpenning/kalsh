#!/usr/bin/env python3
"""CLI to illustrate the order chain and field coverage using fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from rich.console import Console
from rich.table import Table

from kalsh.order_chain import (
    FIELD_DESCRIPTIONS,
    METADATA_STRATEGY,
    ORDER_CHAIN_STEPS,
    TRADE_FIELD_REQUIREMENTS,
    evaluate_trade_field_coverage,
    missing_trade_fields,
)

console = Console()
FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "order_chain"


def _load_fixture(name: str) -> dict[str, Iterable[dict[str, object]]]:
    path = FIXTURE_DIR / name
    with path.open() as handle:
        return json.load(handle)


def _format_params(params: Iterable[str] | Sequence[str]) -> str:
    return ", ".join(params)


def _format_filters(filters: Mapping[str, object]) -> str:
    return ", ".join(f"{key}={value}" for key, value in filters.items())


def main() -> None:
    console.rule("[bold]Order Chain Overview[/bold]")
    steps_table = Table(show_lines=True)
    steps_table.add_column("Step")
    steps_table.add_column("Path")
    steps_table.add_column("Required params")
    steps_table.add_column("Recommended filters")
    steps_table.add_column("Description")

    for step in ORDER_CHAIN_STEPS:
        steps_table.add_row(
            step.name,
            step.path,
            _format_params(step.required_params),
            _format_filters(step.recommended_filters),
            step.description,
        )

    console.print(steps_table)

    console.rule("[bold]Trade field coverage[/bold]")
    trades_payload = _load_fixture("list_trades_sample.json")
    trades = trades_payload.get("trades", [])
    coverage = evaluate_trade_field_coverage(trades)
    coverage_table = Table(show_lines=True)
    coverage_table.add_column("Field")
    coverage_table.add_column("Present", justify="center")
    coverage_table.add_column("Notes")

    for field in TRADE_FIELD_REQUIREMENTS:
        coverage_table.add_row(
            field,
            "[green]yes" if coverage.get(field) else "[red]no",
            FIELD_DESCRIPTIONS.get(field, ""),
        )

    console.print(coverage_table)

    missing = missing_trade_fields(trades)
    if missing:
        console.print("[yellow]Missing trade fields: [/]" + ", ".join(missing))
    else:
        console.print("[green]All required trade fields are present in the sample payload.[/]")

    console.rule("[bold]Metadata strategy[/bold]")
    console.print(METADATA_STRATEGY)


if __name__ == "__main__":
    main()
