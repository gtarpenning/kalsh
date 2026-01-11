"""Top-market anomaly detection pipeline.

Note on User Identification:
    The Kalshi public API may not expose user_id/account_id fields in trade data
    for privacy reasons. When user identifiers are unavailable, trades are marked
    as "anonymous" and those markets are skipped during detection since we cannot
    attribute trades to specific actors.
    
    Use --debug-payload flag with run_pipeline.py to inspect actual API fields.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime
from typing import List, Mapping, Sequence

from rich.console import Console
from rich.table import Table

from . import rules, storage
from .client import KalshiClient
from .ingestion import KalshiIngestor


def storage_trade_to_rule_trade(trade: storage.Trade) -> rules.Trade:
    """Convert storage.Trade to rules.Trade for detection."""
    return rules.Trade(
        market_id=trade.market_id,
        user_id=trade.user_id,
        quantity=int(trade.quantity),
    )


@dataclass(frozen=True)
class DetectionCase:
    """Represents a detected anomaly case."""

    market_id: str
    user_id: str
    window_id: int
    rule: str
    reason: Mapping[str, object]
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "market_id": self.market_id,
            "user_id": self.user_id,
            "window_id": self.window_id,
            "rule": self.rule,
            "reason": dict(self.reason),
        }


@dataclass(frozen=True)
class MarketResult:
    """Result of processing a single market."""
    
    market_id: str
    name: str
    trade_count: int
    cases: List[DetectionCase]
    skipped: bool = False
    skip_reason: str | None = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "market_id": self.market_id,
            "name": self.name,
            "trade_count": self.trade_count,
            "anomaly_count": len(self.cases),
            "cases": [case.to_dict() for case in self.cases],
            "skipped": self.skipped,
            "skip_reason": self.skip_reason,
        }


@dataclass(frozen=True)
class PipelineResult:
    """Complete result of a pipeline run."""
    
    total_markets: int
    markets_processed: int
    total_cases: int
    market_results: List[MarketResult]
    config: PipelineConfig
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "total_markets": self.total_markets,
            "markets_processed": self.markets_processed,
            "total_cases": self.total_cases,
            "markets": [m.to_dict() for m in self.market_results],
            "config": {
                "market_limit": self.config.market_limit,
                "window_size": self.config.window_size,
                "dominance_threshold": self.config.dominance_threshold,
                "sudden_growth_threshold": self.config.sudden_growth_threshold,
            },
        }


@dataclass(frozen=True)
class PipelineConfig:
    """Configuration for pipeline run.
    
    Parameters:
        market_limit: Maximum number of markets to process (default: 100)
        markets_per_page: Page size for list_markets requests (default: 100)
        trades_per_page: Page size for list_trades requests (default: 500)
        window_size: Sliding window size for feature aggregation (default: 10)
        dominance_threshold: Volume share threshold for dominance rule (default: 0.75)
        sudden_growth_threshold: Net share growth threshold for sudden_growth rule (default: 4)
    
    Notes:
        - Increasing window_size reduces noise but requires more trades per market
        - Lowering dominance_threshold increases sensitivity (more cases detected)
        - trades_per_page affects rate limit overhead; 500 is recommended for speed
    """

    market_limit: int = 100
    markets_per_page: int = 100
    trades_per_page: int = 500
    window_size: int = 10
    dominance_threshold: float = 0.75
    sudden_growth_threshold: int = 4


class PipelineRunner:
    """Orchestrates the full detection pipeline."""

    def __init__(
        self,
        client: KalshiClient,
        store: storage.Store,
        config: PipelineConfig | None = None,
    ):
        self._client = client
        self._store = store
        self._ingestor = KalshiIngestor(client, store)
        self._config = config or PipelineConfig()
        self._console = Console()

    def sync_all_markets(self, status: str | None = None) -> dict[str, int]:
        """Sync all markets from Kalshi API to local database.
        
        Args:
            status: Filter markets by status (open, closed, settled, or None for all)
            
        Returns:
            Dictionary with sync statistics
        """
        start_time = time.time()
        
        self._ingestor.ingest_markets(status=status, per_page=1000)
        
        if isinstance(self._store, storage.SQLiteStore):
            conn = self._store._conn
            cursor = conn.execute("SELECT COUNT(*) FROM markets")
            total_markets = cursor.fetchone()[0]
            
            if status:
                cursor = conn.execute("SELECT COUNT(*) FROM markets WHERE status = ?", (status,))
                status_markets = cursor.fetchone()[0]
            else:
                status_markets = total_markets
        else:
            total_markets = 0
            status_markets = 0
        
        elapsed = time.time() - start_time
        rate = total_markets / elapsed if elapsed > 0 else 0
        
        return {
            "total_markets": total_markets,
            "status_markets": status_markets,
            "elapsed_seconds": elapsed,
            "rate": rate,
        }

    def run(
        self, *, market_status: str = "open", dry_run: bool = False, return_detailed: bool = False, top_trades_mode: bool = False
    ) -> List[DetectionCase] | PipelineResult:
        """Run the full pipeline and return detected cases.
        
        Args:
            market_status: Filter markets by status (default: "open")
            dry_run: Skip trade ingestion if True
            return_detailed: Return PipelineResult with full market details instead of just cases
            top_trades_mode: Show trading activity instead of anomaly detection
            
        Returns:
            List of DetectionCase objects, or PipelineResult if return_detailed=True
        """

        mode_title = "Top Trading Markets" if top_trades_mode else "Kalshi Anomaly Detection Pipeline"
        self._console.rule(f"[bold cyan]{mode_title}")
        
        status_display = market_status if market_status != "all" else "all"
        self._console.print(
            f"Fetching up to {self._config.market_limit} {status_display} markets..."
        )

        markets = self._fetch_markets(market_status)
        self._console.print(f"[green]Found {len(markets)} markets\n")

        if dry_run:
            self._console.print("[yellow]Dry run mode - skipping trade ingestion")
            self._display_market_summary(markets)
            if return_detailed:
                return PipelineResult(
                    total_markets=len(markets),
                    markets_processed=0,
                    total_cases=0,
                    market_results=[],
                    config=self._config,
                )
            return []
        
        if top_trades_mode:
            self._run_top_trades_mode(markets)
            return []

        all_cases: List[DetectionCase] = []
        market_results: List[MarketResult] = []

        for idx, market in enumerate(markets, start=1):
            self._display_market_info(market, idx, len(markets))
            cases, trade_count, skip_info = self._process_market_detailed(market.market_id)
            all_cases.extend(cases)
            
            market_results.append(MarketResult(
                market_id=market.market_id,
                name=market.name,
                trade_count=trade_count,
                cases=cases,
                skipped=skip_info[0] if skip_info else False,
                skip_reason=skip_info[1] if skip_info else None,
            ))

        self._console.print(f"\n[bold green]Detection complete: {len(all_cases)} cases")
        
        if return_detailed:
            return PipelineResult(
                total_markets=len(markets),
                markets_processed=len([m for m in market_results if not m.skipped]),
                total_cases=len(all_cases),
                market_results=market_results,
                config=self._config,
            )
        
        return all_cases
    
    def _display_market_summary(self, markets: List[storage.Market]) -> None:
        """Display summary table of markets."""
        table = Table(title="Markets Overview", show_lines=False)
        table.add_column("#", justify="right", style="dim")
        table.add_column("Ticker", style="cyan")
        table.add_column("Title", style="white", max_width=40)
        table.add_column("Volume", justify="right", style="green")
        table.add_column("Liquidity", justify="right", style="blue")
        table.add_column("Spread", justify="right", style="yellow")
        
        for idx, market in enumerate(markets, start=1):
            volume_str = f"{int(market.volume):,}" if market.volume else "—"
            liquidity_str = f"{int(market.liquidity):,}" if market.liquidity else "—"
            
            if market.yes_bid and market.yes_ask:
                spread = market.yes_ask - market.yes_bid
                spread_str = f"{spread:.0f}¢"
            else:
                spread_str = "—"
            
            table.add_row(
                str(idx),
                market.market_id,
                market.name[:40] if market.name else "—",
                volume_str,
                liquidity_str,
                spread_str,
            )
        
        self._console.print(table)
    
    def _display_market_info(self, market: storage.Market, idx: int, total: int) -> None:
        """Display detailed info for a market being processed."""
        self._console.print(f"\n[bold cyan]Market {idx}/{total}[/]")
        self._console.print(f"  Ticker: [cyan]{market.market_id}[/]")
        self._console.print(f"  Title:  [white]{market.name}[/]")
        
        if market.volume or market.liquidity:
            stats = []
            if market.volume:
                stats.append(f"Vol: {int(market.volume):,}")
            if market.liquidity:
                stats.append(f"Liq: {int(market.liquidity):,}")
            if market.yes_bid and market.no_bid:
                stats.append(f"Yes: {market.yes_bid:.0f}¢ | No: {market.no_bid:.0f}¢")
            self._console.print(f"  [dim]{' • '.join(stats)}[/]")

    def _fetch_markets(self, market_status: str) -> List[storage.Market]:
        """Fetch markets and store them, sorted by volume."""
        status_filter = None if market_status == "all" else market_status
        
        self._ingestor.ingest_markets(
            status=status_filter, per_page=self._config.markets_per_page
        )

        response = self._client.list_markets(
            status=status_filter, per_page=self._config.markets_per_page
        )
        
        markets_with_metrics = []
        for market in response.markets:
            volume = market.volume or 0
            open_interest = market.open_interest or 0
            liquidity = market.liquidity or 0
            
            market_obj = storage.Market(
                market_id=market.ticker,
                name=market.title,
                volume=volume,
                liquidity=liquidity,
                yes_bid=market.yes_bid,
                yes_ask=market.yes_ask,
                no_bid=market.no_bid,
                no_ask=market.no_ask,
            )
            
            markets_with_metrics.append({
                'market': market_obj,
                'volume': volume,
                'open_interest': open_interest,
            })
        
        sorted_markets = sorted(
            markets_with_metrics, 
            key=lambda x: (x['volume'], x['open_interest']), 
            reverse=True
        )
        
        return [item['market'] for item in sorted_markets[:self._config.market_limit]]

    def _process_market(self, market_id: str) -> List[DetectionCase]:
        """Ingest trades for a market and run detection."""
        cases, _, _ = self._process_market_detailed(market_id)
        return cases
    
    def _process_market_detailed(
        self, market_id: str
    ) -> tuple[List[DetectionCase], int, tuple[bool, str] | None]:
        """Ingest trades for a market and run detection, returning detailed info.
        
        Returns:
            Tuple of (cases, trade_count, skip_info)
            where skip_info is (is_skipped, reason) or None if not skipped
        """
        try:
            self._ingestor.ingest_trades(
                market_id, per_page=self._config.trades_per_page
            )
        except Exception as exc:
            self._console.print(
                f"[yellow]  ⚠ Skipping: ingestion failed ({exc})"
            )
            return [], 0, (True, f"ingestion_failed: {exc}")

        stored_trades = list(self._store.iter_trades(market_id, 0, int(time.time() * 1000)))

        if not stored_trades:
            self._console.print("[dim]  No trades found[/]")
            return [], 0, (True, "no_trades")

        self._display_trade_summary(stored_trades)

        if len(stored_trades) < self._config.window_size:
            self._console.print(
                f"[yellow]  ⚠ Insufficient trades ({len(stored_trades)} < {self._config.window_size})[/]"
            )
            return [], len(stored_trades), (True, f"insufficient_trades: {len(stored_trades)} < {self._config.window_size}")

        anonymous_count = sum(1 for t in stored_trades if t.user_id == "anonymous")
        if anonymous_count == len(stored_trades):
            self._console.print(
                "[yellow]  ⚠ All trades anonymous (no user attribution possible)[/]"
            )
            return [], len(stored_trades), (True, "all_anonymous")

        rule_trades = [storage_trade_to_rule_trade(t) for t in stored_trades]

        builder = rules.FeatureBuilder(window_size=self._config.window_size)
        windows = builder.build(rule_trades)

        rule_filter = rules.RuleFilter(
            dominance_threshold=self._config.dominance_threshold,
            sudden_growth_threshold=self._config.sudden_growth_threshold,
        )
        raw_cases = rule_filter.apply(windows)

        if raw_cases:
            self._console.print(f"[bold green]  ✓ Found {len(raw_cases)} anomaly case(s)![/]")
        else:
            self._console.print("[dim]  No anomalies detected[/]")

        cases = [
            DetectionCase(
                market_id=case["market_id"],
                user_id=case["user_id"],
                window_id=case["window_id"],
                rule=case["rule"],
                reason=case["reason"],
            )
            for case in raw_cases
        ]
        
        return cases, len(stored_trades), None
    
    def _run_top_trades_mode(self, markets: List[storage.Market]) -> None:
        """Run in top trades mode - show markets with most trading activity."""
        self._console.print("[bold cyan]Fetching trades from the exchange...\n")
        
        self._console.print(f"[dim]Fetching up to {self._config.market_limit * 100} recent trades...[/]")
        
        from collections import defaultdict
        trades_by_market = defaultdict(list)
        
        try:
            trades_resp = self._client.list_trades(limit=1000)
            all_trades = trades_resp.trades
            
            self._console.print(f"[green]Found {len(all_trades)} recent trades[/]\n")
            
            for trade in all_trades:
                trade_obj = storage.Trade(
                    trade_id=trade.trade_id,
                    market_id=trade.ticker,
                    user_id="anonymous",
                    price=trade.price,
                    quantity=float(trade.count),
                    timestamp=int(trade.created_time.timestamp() * 1000),
                )
                trades_by_market[trade.ticker].append(trade_obj)
            
            self._console.print(f"[dim]Fetching market details for {len(trades_by_market)} tickers...[/]\n")
            
            market_details = {}
            unique_tickers = list(trades_by_market.keys())
            for ticker in unique_tickers[:100]:
                try:
                    markets_resp = self._client.list_markets(per_page=1000)
                    for mkt in markets_resp.markets:
                        if mkt.ticker in trades_by_market:
                            market_details[mkt.ticker] = mkt.title
                    break
                except Exception:
                    market_details[ticker] = ticker
            
            markets_with_trades = []
            for ticker, trades in trades_by_market.items():
                total_volume = sum(t.quantity for t in trades)
                total_value = sum(t.quantity * t.price for t in trades)
                
                market_name = market_details.get(ticker, ticker)
                
                markets_with_trades.append({
                    'ticker': ticker,
                    'name': market_name,
                    'trades': trades,
                    'volume': total_volume,
                    'value': total_value,
                    'trade_count': len(trades),
                })
            
            if not markets_with_trades:
                self._console.print("[yellow]No markets with trades found")
                return
            
            sorted_by_volume = sorted(
                markets_with_trades, 
                key=lambda x: x['volume'], 
                reverse=True
            )[:self._config.market_limit]
            
            self._console.print(f"[bold green]Top {len(sorted_by_volume)} markets by volume\n")
            
            total_all_trades = sum(item['trade_count'] for item in sorted_by_volume)
            total_all_volume = sum(item['volume'] for item in sorted_by_volume)
            total_all_value = sum(item['value'] for item in sorted_by_volume)
            
            for idx, item in enumerate(sorted_by_volume, start=1):
                self._console.rule(f"[bold cyan]#{idx}: {item['ticker']}")
                self._console.print(f"[white]{item['name']}[/]")
                self._console.print(
                    f"[green]{item['trade_count']} trades[/] • "
                    f"[blue]Vol: {int(item['volume']):,} contracts[/] • "
                    f"[magenta]Value: ${item['value']:,.2f}[/]"
                )
                
                self._display_trade_details(item['trades'])
                self._console.print()
            
            self._console.rule("[bold green]Summary")
            self._console.print(
                f"[bold]Total across top {len(sorted_by_volume)} markets:[/]\n"
                f"  • {total_all_trades:,} trades\n"
                f"  • {int(total_all_volume):,} contracts\n"
                f"  • ${total_all_value:,.2f} total value"
            )
                
        except Exception as exc:
            self._console.print(f"[red]Failed to fetch trades: {exc}")
            raise
    
    def _display_trade_details(self, trades: List[storage.Trade]) -> None:
        """Display detailed trade information."""
        top_trades = sorted(trades, key=lambda t: t.quantity, reverse=True)[:5]
        
        if top_trades:
            self._console.print("\n[bold]Largest Trades:[/]")
            for i, trade in enumerate(top_trades, start=1):
                trade_value = trade.quantity * trade.price
                user_display = trade.user_id[:16] + "..." if len(trade.user_id) > 19 else trade.user_id
                timestamp = datetime.fromtimestamp(trade.timestamp / 1000).strftime("%Y-%m-%d %H:%M:%S")
                
                self._console.print(
                    f"  {i}. [cyan]{int(trade.quantity):,}[/] contracts @ "
                    f"[yellow]${trade.price:.2f}[/] = "
                    f"[magenta]${trade_value:,.2f}[/] • "
                    f"[white]{timestamp}[/] • "
                    f"[dim]{user_display}[/]"
                )
    
    def _display_trade_summary(self, trades: List[storage.Trade]) -> None:
        """Display summary of trades for a market."""
        if not trades:
            return
        
        total_volume = sum(t.quantity for t in trades)
        avg_price = sum(t.price for t in trades) / len(trades)
        total_value = sum(t.quantity * t.price for t in trades)
        
        unique_users = len(set(t.user_id for t in trades if t.user_id != "anonymous"))
        
        top_trades = sorted(trades, key=lambda t: t.quantity, reverse=True)[:5]
        
        self._console.print(
            f"  [green]{len(trades)} trades[/] • "
            f"[blue]Vol: {int(total_volume):,} contracts[/] • "
            f"[magenta]Value: ${total_value:,.2f}[/] • "
            f"[yellow]Avg: ${avg_price:.2f}[/] • "
            f"[cyan]Users: {unique_users}[/]"
        )
        
        if top_trades:
            self._console.print("  [bold]Largest Trades (by contract count):[/]")
            for i, trade in enumerate(top_trades, start=1):
                trade_value = trade.quantity * trade.price
                user_display = trade.user_id[:16] + "..." if len(trade.user_id) > 19 else trade.user_id
                timestamp = datetime.fromtimestamp(trade.timestamp / 1000).strftime("%Y-%m-%d %H:%M:%S")
                
                self._console.print(
                    f"    {i}. [cyan]{int(trade.quantity):,}[/] contracts @ "
                    f"[yellow]${trade.price:.2f}[/] = "
                    f"[magenta]${trade_value:,.2f}[/] • "
                    f"[white]{timestamp}[/] • "
                    f"[dim]{user_display}[/]"
                )


class PipelineReporter:
    """Reports detection results in rich format."""

    def __init__(self, console: Console | None = None):
        self._console = console or Console()

    def report_cases(
        self, cases: Sequence[DetectionCase], *, sort_by: str = "market_id"
    ) -> None:
        """Display detection cases in a rich table."""

        if not cases:
            self._console.print("[yellow]No anomaly cases detected.")
            return

        sorted_cases = self._sort_cases(cases, sort_by)

        table = Table(title="Detected Anomaly Cases", show_lines=True)
        table.add_column("Market ID", style="cyan")
        table.add_column("User ID", style="yellow")
        table.add_column("Rule", style="magenta")
        table.add_column("Window", justify="right")
        table.add_column("Details", style="dim")

        for case in sorted_cases:
            details = self._format_reason(case.reason)
            table.add_row(
                case.market_id,
                case.user_id,
                case.rule,
                str(case.window_id),
                details,
            )

        self._console.print(table)
        self._print_summary(sorted_cases)
    
    def report_json(self, cases: Sequence[DetectionCase], *, sort_by: str = "market_id") -> str:
        """Return detection cases as JSON string."""
        sorted_cases = self._sort_cases(cases, sort_by)
        return json.dumps(
            {
                "total_cases": len(sorted_cases),
                "cases": [case.to_dict() for case in sorted_cases],
                "summary": self._generate_summary(sorted_cases),
            },
            indent=2,
        )

    def _sort_cases(
        self, cases: Sequence[DetectionCase], sort_by: str
    ) -> List[DetectionCase]:
        """Sort cases by specified field."""
        if sort_by == "rule":
            return sorted(cases, key=lambda c: (c.rule, c.market_id))
        return sorted(cases, key=lambda c: (c.market_id, c.window_id))

    def _format_reason(self, reason: Mapping[str, object]) -> str:
        """Format reason details for display."""
        rule = reason.get("rule")
        if rule == "dominance":
            share = reason.get("share")
            if isinstance(share, (list, tuple)) and len(share) == 2:
                pct = (share[0] / share[1]) * 100
                return f"share={pct:.1f}%"
            return "dominance detected"
        if rule == "sudden_growth":
            growth = reason.get("growth")
            return f"growth={growth}"
        return str(reason)

    def _generate_summary(self, cases: Sequence[DetectionCase]) -> dict[str, int]:
        """Generate summary statistics."""
        rule_counts: dict[str, int] = {}
        for case in cases:
            rule_counts[case.rule] = rule_counts.get(case.rule, 0) + 1
        return rule_counts
    
    def _print_summary(self, cases: Sequence[DetectionCase]) -> None:
        """Print summary statistics."""
        rule_counts = self._generate_summary(cases)
        self._console.print("\n[bold]Summary:[/]")
        for rule, count in sorted(rule_counts.items()):
            self._console.print(f"  {rule}: {count} case(s)")
