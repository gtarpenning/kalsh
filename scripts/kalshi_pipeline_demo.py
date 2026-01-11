#!/usr/bin/env python3
from __future__ import annotations

import sys
from dataclasses import asdict, dataclass
from typing import Any, Dict, List

from rich.console import Console
from rich.prompt import FloatPrompt, Prompt
from rich.table import Table

from kalsh.client import KalshiClient, KalshiEnvironment
from kalsh.env import KalshiCredentials

console = Console()


@dataclass
class Market:
    ticker: str
    event_ticker: str
    title: str
    status: str
    close_time: str
    expiration_time: str
    market_type: str
    liquidity: float
    volume: float
    yes_bid: float
    no_bid: float
    yes_ask: float
    no_ask: float
    rules_primary: str
    rules_secondary: str
    price_ranges: List[Dict[str, str]]
    settlement_timer_seconds: int
    notional_value: float
    open_time: str
    expected_expiration_time: str
    latest_expiration_time: str


@dataclass
class Trade:
    trade_id: str
    market_id: str
    price: float
    quantity: float
    timestamp: int


class LivePipeline:
    def __init__(self, client: KalshiClient) -> None:
        self.client = client
        self.stage_options = (
            "Raw payload pages",
            "Normalized markets",
            "Normalized trades",
        )
        self.trace: dict[str, List[Any]] = {"raw_pages": [], "markets": [], "trades": []}
        self.request_log: List[Dict[str, Any]] = []

    def clear_trace(self) -> None:
        self.trace["raw_pages"].clear()
        self.trace["markets"].clear()
        self.trace["trades"].clear()
        self.request_log.clear()

    def _record_raw(self, source: str, payload: Any) -> None:
        self.trace["raw_pages"].append({"source": source, "payload": payload})

    def _log_request(self, method: str, path: str, params: Dict[str, Any] | None) -> None:
        self.request_log.append({"method": method, "path": path, "params": dict(params or {})})

    def capture(
        self,
        market_id: str,
        markets_response: dict[str, Any] | None = None,
        market_params: Dict[str, Any] | None = None,
    ) -> None:
        self.clear_trace()

        market_params = market_params or {"per_page": 50}
        if markets_response is None:
            markets_response = self.client.list_markets(**market_params)
        if error := markets_response.get("error"):
            raise RuntimeError(f"list_markets error: {error}")
        self._log_request("GET", KalshiClient.MARKETS_PATH, market_params)
        self._record_raw("list_markets", markets_response)
        markets = [
            Market(
                ticker=entry["ticker"],
                event_ticker=entry["event_ticker"],
                title=entry["title"],
                status=entry["status"],
                close_time=entry["close_time"],
                expiration_time=entry["expiration_time"],
                market_type=entry["market_type"],
                liquidity=float(entry["liquidity"]),
                volume=float(entry["volume"]),
                yes_bid=float(entry.get("yes_bid", 0)),
                no_bid=float(entry.get("no_bid", 0)),
                yes_ask=float(entry.get("yes_ask", 0)),
                no_ask=float(entry.get("no_ask", 0)),
                rules_primary=entry.get("rules_primary", ""),
                rules_secondary=entry.get("rules_secondary", ""),
                price_ranges=entry.get("price_ranges", []),
                settlement_timer_seconds=int(entry.get("settlement_timer_seconds", 0)),
                notional_value=float(entry.get("notional_value", 0)),
                open_time=entry.get("open_time", ""),
                expected_expiration_time=entry.get("expected_expiration_time", ""),
                latest_expiration_time=entry.get("latest_expiration_time", ""),
            )
            for entry in markets_response.get("markets", [])
        ]
        self.trace["markets"].extend(markets)

        next_cursor: str | None = None
        while True:
            trade_params: Dict[str, Any] = {"market_id": market_id, "per_page": 5}
            if next_cursor:
                trade_params["cursor"] = next_cursor
            trades_response = self.client.list_trades(**trade_params)
            self._log_request("GET", KalshiClient.TRADES_PATH, trade_params)
            self._record_raw("list_trades", trades_response)
            trades = [
                Trade(
                    trade_id=entry["trade_id"],
                    market_id=entry["market_id"],
                    price=float(entry["price"]),
                    quantity=float(entry["quantity"]),
                    timestamp=int(entry["timestamp"]),
                )
                for entry in trades_response.get("trades", [])
            ]
            self.trace["trades"].extend(trades)
            next_cursor = trades_response.get("next_cursor")
            if not next_cursor:
                break


def display_raw_pages(pipeline: LivePipeline) -> None:
    console.rule("[bold]Raw payload pages")
    raw_pages = pipeline.trace["raw_pages"]
    if not raw_pages:
        console.print("[yellow]Capture a feed to populate raw payload pages.")
        return
    for idx, record in enumerate(raw_pages, start=1):
        console.print(f"[bold]Page {idx} — {record['source']}[/]")
        console.print_json(data=record["payload"])


def display_markets(pipeline: LivePipeline) -> None:
    console.rule("[bold]Normalized markets")
    markets: List[Market] = pipeline.trace["markets"]
    if not markets:
        console.print("[yellow]No normalized markets recorded yet.")
        return
    table = Table(title="Normalized markets", show_lines=True)
    table.add_column("ticker")
    table.add_column("title")
    table.add_column("status")
    table.add_column("close time")
    table.add_column("liquidity", justify="right")
    table.add_column("volume", justify="right")
    table.add_column("yes bid", justify="right")
    table.add_column("no bid", justify="right")
    for market in markets:
        table.add_row(
            market.ticker,
            market.title,
            market.status,
            market.close_time,
            f"{market.liquidity:.2f}",
            f"{market.volume:.2f}",
            f"{market.yes_bid:.2f}",
            f"{market.no_bid:.2f}",
        )
    console.print(table)


def display_trades(pipeline: LivePipeline, threshold: float) -> None:
    console.rule("[bold]Normalized trades")
    trades: List[Trade] = pipeline.trace["trades"]
    if not trades:
        console.print("[yellow]No trades recorded yet.")
        return

    table = Table(title="Trades", show_lines=True)
    table.add_column("trade_id")
    table.add_column("price", justify="right")
    table.add_column("quantity", justify="right")
    table.add_column("classification", justify="center")
    for trade in trades:
        classification = "Large" if trade.quantity >= threshold else "Small"
        table.add_row(
            trade.trade_id,
            f"{trade.price:.2f}",
            f"{trade.quantity:.2f}",
            classification,
        )
    console.print(table)

    large_count = sum(1 for trade in trades if trade.quantity >= threshold)
    console.print(
        f"- {large_count} large trade(s) (≥ {threshold} quantity)\n"
        f"- {len(trades) - large_count} small trade(s)"
    )

    inspect_choice = Prompt.ask(
        "Inspect trade payload",
        choices=[trade.trade_id for trade in trades],
        default=trades[0].trade_id,
    )
    selected_trade = next(trade for trade in trades if trade.trade_id == inspect_choice)
    console.print("**Selected trade payload**")
    console.print_json(data=asdict(selected_trade))


def display_recent_requests(pipeline: LivePipeline) -> None:
    if not pipeline.request_log:
        return
    console.print("\n[bold]Recent mock requests[/]")
    recent = pipeline.request_log[-5:]
    for entry in recent:
        console.print(f"{entry['method']} {entry['path']} → {entry['params']}")


def choose_stage(pipeline: LivePipeline) -> str:
    return Prompt.ask(
        "Select stage to inspect",
        choices=list(pipeline.stage_options),
        default=pipeline.stage_options[0],
    )


def adjust_threshold(current: float) -> float:
    return FloatPrompt.ask(
        "Large trade quantity threshold",
        default=current,
        show_default=True,
    )


def gather_market_choices(pipeline: LivePipeline) -> tuple[str, dict[str, Any], Dict[str, Any]] | None:
    market_params = {"per_page": 100}
    try:
        markets_response = pipeline.client.list_markets(**market_params)
    except Exception as exc:
        console.print(f"[red]Failed to load markets: {exc}")
        return None
    if error := markets_response.get("error"):
        console.print(f"[red]API refused to list markets: {error}")
        return None
    market_ids = [entry["market_id"] for entry in markets_response.get("markets", [])]
    if not market_ids:
        console.print("[yellow]No markets returned from the API.")
        return None
    market_id = Prompt.ask(
        "Market to explore",
        choices=market_ids,
        default=market_ids[0],
    )
    return market_id, markets_response, market_params


def build_pipeline() -> LivePipeline | None:
    try:
        credentials = KalshiCredentials.from_env()
    except EnvironmentError as exc:
        console.print(f"[red]Credentials missing: {exc}")
        console.print("[yellow]Set KALSHI_API_KEY and KALSHI_API_SECRET (or *_FILE) and retry.")
        return None

    environment_choice = Prompt.ask(
        "Environment",
        choices=["demo", "prod"],
        default="demo",
    )
    environment = (
        KalshiEnvironment.PROD if environment_choice == "prod" else KalshiEnvironment.DEMO
    )
    client = KalshiClient(credentials=credentials, environment=environment)
    return LivePipeline(client)


def main() -> None:
    console.rule("[bold blue]Kalshi pipeline explorer")
    pipeline = build_pipeline()
    if pipeline is None:
        sys.exit(1)

    threshold = 2.5

    while True:
        console.print("\n[bold]Available actions[/]")
        console.print("1) Capture pipeline feed")
        console.print("2) Inspect a stage")
        console.print("3) Adjust large-trade threshold")
        console.print("4) Exit")
        action = Prompt.ask("Choose an action", choices=["1", "2", "3", "4"], default="2")

        if action == "1":
            choice = gather_market_choices(pipeline)
            if not choice:
                continue
            market_id, markets_response, market_params = choice
            try:
                pipeline.capture(market_id, markets_response, market_params)
                console.print("[green]Captured pipeline feed from Kalshi.[/]")
            except Exception as exc:
                console.print(f"[red]Capture failed: {exc}")
        elif action == "2":
            stage = choose_stage(pipeline)
            if stage == "Raw payload pages":
                display_raw_pages(pipeline)
            elif stage == "Normalized markets":
                display_markets(pipeline)
            else:
                display_trades(pipeline, threshold)
            display_recent_requests(pipeline)
        elif action == "3":
            threshold = adjust_threshold(threshold)
            console.print(f"Threshold set to {threshold:.2f}")
        else:
            console.print("See you next time! 🌊")
            break


if __name__ == "__main__":
    main()

