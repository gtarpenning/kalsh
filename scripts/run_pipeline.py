#!/usr/bin/env python3
"""CLI runner for the top-market anomaly detection pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console

from kalsh.client import KalshiClient, KalshiEnvironment
from kalsh.env import KalshiCredentials
from kalsh.pipeline import PipelineConfig, PipelineReporter, PipelineRunner
from kalsh.storage import SQLiteStore

console = Console()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Kalshi anomaly detection pipeline"
    )
    parser.add_argument(
        "--db",
        type=str,
        default="kalshi_pipeline.db",
        help="SQLite database path (default: kalshi_pipeline.db)",
    )
    parser.add_argument(
        "--env",
        type=str,
        choices=["demo", "prod"],
        default="demo",
        help="Kalshi environment (default: demo)",
    )
    parser.add_argument(
        "--market-limit",
        type=int,
        default=100,
        help="Maximum number of markets to process (default: 100)",
    )
    parser.add_argument(
        "--market-status",
        type=str,
        default="open",
        help="Market status filter (default: open, use 'all' for no filter)",
    )
    parser.add_argument(
        "--window-size",
        type=int,
        default=10,
        help="Sliding window size for detection (default: 10)",
    )
    parser.add_argument(
        "--dominance-threshold",
        type=float,
        default=0.75,
        help="Dominance rule threshold (default: 0.75)",
    )
    parser.add_argument(
        "--growth-threshold",
        type=int,
        default=4,
        help="Sudden growth threshold (default: 4)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch markets only, skip trade ingestion",
    )
    parser.add_argument(
        "--sort-by",
        type=str,
        choices=["market_id", "rule"],
        default="market_id",
        help="Sort results by field (default: market_id)",
    )
    parser.add_argument(
        "--debug-payload",
        action="store_true",
        help="Print sample trade payload to inspect available fields",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        metavar="FILE",
        help="Save results as JSON to specified file",
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["table", "json"],
        default="table",
        help="Output format: table (rich display) or json (stdout)",
    )
    parser.add_argument(
        "--top-trades-mode",
        action="store_true",
        help="Show markets with most trading activity instead of anomaly detection",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        credentials = KalshiCredentials.from_env()
    except EnvironmentError as exc:
        console.print(f"[red]Error: {exc}")
        console.print(
            "[yellow]Set KALSHI_API_KEY and KALSHI_API_SECRET (or *_FILE) environment variables"
        )
        sys.exit(1)

    environment = (
        KalshiEnvironment.PROD if args.env == "prod" else KalshiEnvironment.DEMO
    )
    db_path = Path(args.db).resolve()

    console.print(f"[dim]Using database: {db_path}")
    console.print(f"[dim]Environment: {environment.name}")

    client = KalshiClient(credentials=credentials, environment=environment)
    store = SQLiteStore(str(db_path))

    config = PipelineConfig(
        market_limit=args.market_limit,
        window_size=args.window_size,
        dominance_threshold=args.dominance_threshold,
        sudden_growth_threshold=args.growth_threshold,
    )

    runner = PipelineRunner(client, store, config)

    if args.debug_payload:
        console.rule("[bold cyan]Debug: Inspecting Trade Payload")
        try:
            markets_resp = client.list_markets(status=args.market_status, per_page=1)
            if markets_resp.markets:
                sample_market = markets_resp.markets[0]
                market_ticker = sample_market.ticker
                console.print(f"[dim]Fetching trades for: {market_ticker}")
                trades_resp = client.list_trades(ticker=market_ticker, limit=1)
                if trades_resp.trades:
                    console.print("\n[bold]Sample Trade Payload:[/]")
                    console.print_json(data=trades_resp.trades[0].model_dump())
                else:
                    console.print("[yellow]No trades available")
            else:
                console.print("[yellow]No markets available")
        except Exception as exc:
            console.print(f"[red]Debug failed: {exc}")
        return

    try:
        use_detailed = bool(args.output_json and not args.dry_run)
        result = runner.run(
            market_status=args.market_status,
            dry_run=args.dry_run,
            return_detailed=use_detailed,
            top_trades_mode=args.top_trades_mode,
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Pipeline interrupted by user")
        sys.exit(130)
    except Exception as exc:
        console.print(f"[red]Pipeline failed: {exc}")
        raise

    if not args.dry_run:
        reporter = PipelineReporter(console)
        
        from kalsh.pipeline import PipelineResult
        if isinstance(result, PipelineResult):
            cases = [case for market in result.market_results for case in market.cases]
        else:
            cases = result
        
        if args.format == "json":
            if isinstance(result, PipelineResult):
                import json
                console.print(json.dumps(result.to_dict(), indent=2))
            else:
                json_output = reporter.report_json(cases, sort_by=args.sort_by)
                console.print(json_output)
        else:
            reporter.report_cases(cases, sort_by=args.sort_by)
        
        if args.output_json:
            import json
            if isinstance(result, PipelineResult):
                output_data = result.to_dict()
            else:
                output_data = {
                    "total_cases": len(cases),
                    "cases": [case.to_dict() for case in cases],
                }
            
            with open(args.output_json, "w") as f:
                json.dump(output_data, f, indent=2)
            console.print(f"\n[green]Results saved to: {args.output_json}")


if __name__ == "__main__":
    main()
