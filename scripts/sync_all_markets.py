#!/usr/bin/env python3
"""Sync all Kalshi markets to local database."""

import argparse
import time
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn

from kalsh.client import KalshiClient, KalshiEnvironment
from kalsh.env import KalshiCredentials, get_kalshi_environment
from kalsh.ingestion import KalshiIngestor
from kalsh.storage import SQLiteStore


def sync_all_markets(
    db_path: str,
    status: str | None = None,
    force: bool = False,
) -> dict[str, int]:
    """Sync all markets from Kalshi API to local database.
    
    Args:
        db_path: Path to SQLite database
        status: Filter markets by status (open, closed, settled, or None for all)
        force: Force refresh even if recently synced
        
    Returns:
        Dictionary with sync statistics
    """
    console = Console()
    
    credentials = KalshiCredentials.from_env()
    env_name = get_kalshi_environment()
    environment = KalshiEnvironment.PROD if env_name == "PROD" else KalshiEnvironment.DEMO
    
    client = KalshiClient(credentials=credentials, environment=environment)
    store = SQLiteStore(db_path)
    ingestor = KalshiIngestor(client, store)
    
    start_time = time.time()
    
    status_display = status if status else "all"
    console.rule(f"[bold cyan]Syncing {status_display} markets from Kalshi")
    
    with Progress(
        SpinnerColumn(),
        *Progress.get_default_columns(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Fetching markets...", total=None)
        
        ingestor.ingest_markets(status=status, per_page=1000)
        
        progress.update(task, completed=True)
    
    conn = store._conn
    cursor = conn.execute("SELECT COUNT(*) FROM markets")
    total_markets = cursor.fetchone()[0]
    
    if status:
        cursor = conn.execute("SELECT COUNT(*) FROM markets WHERE status = ?", (status,))
        status_markets = cursor.fetchone()[0]
    else:
        status_markets = total_markets
    
    elapsed = time.time() - start_time
    rate = total_markets / elapsed if elapsed > 0 else 0
    
    console.print(f"\n[bold green]✓ Sync complete!")
    console.print(f"  • Total markets in DB: {total_markets:,}")
    console.print(f"  • Markets with status '{status_display}': {status_markets:,}")
    console.print(f"  • Time taken: {elapsed:.2f}s")
    console.print(f"  • Rate: {rate:.1f} markets/sec")
    
    return {
        "total_markets": total_markets,
        "status_markets": status_markets,
        "elapsed_seconds": elapsed,
        "rate": rate,
    }


def main():
    parser = argparse.ArgumentParser(description="Sync all Kalshi markets to local database")
    parser.add_argument(
        "--db",
        default="kalshi_pipeline.db",
        help="Path to SQLite database (default: kalshi_pipeline.db)",
    )
    parser.add_argument(
        "--status",
        choices=["open", "closed", "settled"],
        help="Filter markets by status (default: all)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force refresh even if recently synced",
    )
    
    args = parser.parse_args()
    
    sync_all_markets(
        db_path=args.db,
        status=args.status,
        force=args.force,
    )


if __name__ == "__main__":
    main()
