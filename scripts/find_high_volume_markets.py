"""Find markets with the highest trading volume and test candlesticks."""

import time
from rich.console import Console
from rich.table import Table
from rich.progress import Progress

from kalsh.client import KalshiClient, KalshiEnvironment
from kalsh.env import KalshiCredentials, get_kalshi_environment

console = Console()

def extract_series_ticker(ticker: str) -> str:
    """Extract series ticker from full market ticker."""
    return ticker.split("-")[0]

if __name__ == "__main__":
    credentials = KalshiCredentials.from_env()
    env_name = get_kalshi_environment()
    environment = KalshiEnvironment.PROD if env_name == "PROD" else KalshiEnvironment.DEMO
    
    console.print(f"\n[bold cyan]Using environment:[/] {env_name} ({environment.value})\n")
    
    client = KalshiClient(
        credentials=credentials,
        environment=environment,
    )
    
    console.print("[yellow]Fetching markets with trading volume...[/]")
    
    all_markets = []
    
    with Progress() as progress:
        task = progress.add_task("[green]Scanning markets...", total=3)
        
        for status in ["open", "closed", "settled"]:
            response = client.list_markets(status=status, per_page=100)
            for market in response.markets:
                if market.volume and market.volume > 0:
                    all_markets.append(market)
            progress.update(task, advance=1)
    
    all_markets.sort(key=lambda m: m.volume or 0, reverse=True)
    
    console.print(f"\n[green]Found {len(all_markets)} markets with trading volume[/]\n")
    
    table = Table(title="Top 15 Markets by Volume", show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=3)
    table.add_column("Ticker", style="cyan", width=40)
    table.add_column("Status", width=10)
    table.add_column("Volume", justify="right", style="green")
    table.add_column("Open Interest", justify="right", style="yellow")
    table.add_column("Title", width=50)
    
    for i, market in enumerate(all_markets[:15], 1):
        status_color = {
            "open": "[green]open[/]",
            "closed": "[yellow]closed[/]",
            "settled": "[dim]settled[/]",
            "determined": "[blue]determined[/]",
        }.get(market.status, market.status)
        
        table.add_row(
            str(i),
            market.ticker[:40],
            status_color,
            f"{market.volume:,}",
            f"{market.open_interest:,}" if market.open_interest else "0",
            market.title[:50] + "..." if len(market.title) > 50 else market.title,
        )
    
    console.print(table)
    
    if not all_markets:
        console.print("[red]No markets with volume found![/]")
        exit(1)
    
    console.print("\n[bold cyan]Testing candlesticks on top market...[/]")
    
    test_market = all_markets[0]
    series_ticker = extract_series_ticker(test_market.ticker)
    
    console.print(f"  Ticker: [cyan]{test_market.ticker}[/]")
    console.print(f"  Extracted Series: [yellow]{series_ticker}[/]")
    console.print(f"  Volume: [green]{test_market.volume:,}[/]")
    console.print(f"  Status: {test_market.status}")
    
    now = int(time.time())
    start_ts = now - (30 * 24 * 60 * 60)
    
    try:
        candles_response = client.get_market_candlesticks(
            series_ticker=series_ticker,
            ticker=test_market.ticker,
            start_ts=start_ts,
            end_ts=now,
            period_interval=1440,
        )
        
        console.print(f"\n[green]✓ Got {len(candles_response.candlesticks)} candlesticks[/]")
        
        if candles_response.candlesticks:
            console.print("\n[bold]Recent candlestick data:[/]")
            for c in candles_response.candlesticks[:5]:
                ts_str = time.strftime('%Y-%m-%d', time.localtime(c.end_period_ts))
                if c.price and c.price.close is not None:
                    console.print(f"  {ts_str}: [yellow]{c.price.close}¢[/] | Vol: [green]{c.volume:,}[/] | OI: [cyan]{c.open_interest:,}[/]")
                else:
                    console.print(f"  {ts_str}: [dim]No price data[/] | Vol: {c.volume:,}")
            
            if len(candles_response.candlesticks) > 5:
                console.print(f"  [dim]... and {len(candles_response.candlesticks) - 5} more[/]")
            
            console.print(f"\n[bold green]✅ Candlestick data available for this market![/]")
            console.print(f"\n[bold]To test in dashboard:[/]")
            console.print(f"  [cyan]http://localhost:3000[/]")
            console.print(f"  Market: [yellow]{test_market.ticker}[/]")
        else:
            console.print("[yellow]No candlestick data for this market[/]")
            console.print("\n[dim]Testing a few more high-volume markets...[/]")
            
            for market in all_markets[1:6]:
                series = extract_series_ticker(market.ticker)
                console.print(f"\n  Trying: {market.ticker[:40]}... (vol: {market.volume:,})")
                try:
                    cr = client.get_market_candlesticks(
                        series_ticker=series,
                        ticker=market.ticker,
                        start_ts=start_ts,
                        end_ts=now,
                        period_interval=1440,
                    )
                    if cr.candlesticks:
                        console.print(f"    [green]✓ Found {len(cr.candlesticks)} candlesticks![/]")
                        console.print(f"    [bold]Market:[/] [yellow]{market.ticker}[/]")
                        break
                    else:
                        console.print("    [dim]✗ No candlesticks[/]")
                except Exception as e:
                    console.print(f"    [red]✗ Error: {str(e)[:50]}[/]")
                    
    except Exception as e:
        console.print(f"\n[red]✗ Error getting candlesticks: {e}[/]")
        import traceback
        traceback.print_exc()
