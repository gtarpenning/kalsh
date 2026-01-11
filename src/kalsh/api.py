"""FastAPI backend for the Kalshi dashboard."""

from __future__ import annotations

import logging
import sqlite3
import time
from typing import Any

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .client import KalshiClient, KalshiEnvironment
from .env import KalshiCredentials, get_kalshi_environment
from .pipeline import PipelineRunner, PipelineConfig
from .storage import SQLiteStore

logger = logging.getLogger(__name__)

app = FastAPI(title="Kalsh API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "kalshi_pipeline.db"


class DashboardData(BaseModel):
    pipelineRuns: list[dict[str, Any]]
    databaseSnapshots: list[dict[str, Any]]
    markets: list[dict[str, Any]]


class PipelineRunResponse(BaseModel):
    status: str
    message: str
    run_id: str | None = None


class MarketsResponse(BaseModel):
    markets: list[dict[str, Any]]
    total: int
    limit: int
    offset: int
    sort_by: str
    sort_order: str
    last_sync: str | None = None


class SyncAllResponse(BaseModel):
    status: str
    message: str
    job_id: str | None = None


def get_db() -> sqlite3.Connection:
    """Get database connection."""
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def count_table_rows(conn: sqlite3.Connection, table: str) -> int:
    """Count rows in a table."""
    try:
        cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
        return cursor.fetchone()[0]
    except sqlite3.OperationalError:
        return 0


def get_markets(
    conn: sqlite3.Connection,
    limit: int = 10,
    offset: int = 0,
    sort_by: str = "volume",
    sort_order: str = "desc",
    status: str | None = None,
    search: str | None = None,
    min_volume: float | None = None,
    max_volume: float | None = None,
    min_liquidity: float | None = None,
    max_liquidity: float | None = None,
) -> tuple[list[dict[str, Any]], int, str | None]:
    """Fetch markets from the database with filtering and sorting.
    
    Returns:
        Tuple of (markets, total_count, last_sync_time)
    """
    try:
        where_clauses = []
        params = []
        
        if status and status != "all":
            where_clauses.append("m.status = ?")
            params.append(status)
        
        if search:
            where_clauses.append("(m.name LIKE ? OR m.market_id LIKE ?)")
            search_pattern = f"%{search}%"
            params.extend([search_pattern, search_pattern])
        
        if min_volume is not None:
            where_clauses.append("COALESCE(m.volume, 0) >= ?")
            params.append(min_volume)
        
        if max_volume is not None:
            where_clauses.append("COALESCE(m.volume, 0) <= ?")
            params.append(max_volume)
        
        if min_liquidity is not None:
            where_clauses.append("COALESCE(m.liquidity, 0) >= ?")
            params.append(min_liquidity)
        
        if max_liquidity is not None:
            where_clauses.append("COALESCE(m.liquidity, 0) <= ?")
            params.append(max_liquidity)
        
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        sort_column_map = {
            "volume": "COALESCE(m.volume, 0)",
            "liquidity": "COALESCE(m.liquidity, 0)",
            "probability": "(COALESCE(m.yes_bid, 0) + COALESCE(m.yes_ask, 0)) / 2.0",
            "last_fetched": "COALESCE(m.last_fetched, 0)",
        }
        sort_column = sort_column_map.get(sort_by, "COALESCE(m.volume, 0)")
        sort_direction = "DESC" if sort_order.lower() == "desc" else "ASC"
        
        count_cursor = conn.execute(
            f"SELECT COUNT(*) FROM markets m WHERE {where_sql}",
            params,
        )
        total_count = count_cursor.fetchone()[0]
        
        last_sync_cursor = conn.execute(
            "SELECT MAX(last_fetched) FROM markets WHERE last_fetched IS NOT NULL"
        )
        last_sync_result = last_sync_cursor.fetchone()
        last_sync = None
        if last_sync_result and last_sync_result[0]:
            from datetime import datetime
            last_sync = datetime.fromtimestamp(last_sync_result[0]).isoformat() + "Z"
        
        cursor = conn.execute(
            f"""
            SELECT 
                m.market_id, m.name, m.status, m.volume, m.liquidity,
                m.yes_bid, m.yes_ask, m.no_bid, m.no_ask, m.close_time, m.series_ticker,
                m.last_fetched,
                COUNT(t.trade_id) as trade_count,
                COALESCE(SUM(t.quantity), 0) as trade_volume
            FROM markets m
            LEFT JOIN trades t ON m.market_id = t.market_id
            WHERE {where_sql}
            GROUP BY m.market_id
            ORDER BY {sort_column} {sort_direction}
            LIMIT ? OFFSET ?
            """,
            params + [limit, offset],
        )
        markets = []
        for row in cursor.fetchall():
            (market_id, name, status, db_volume, liquidity,
             yes_bid, yes_ask, no_bid, no_ask, close_time, series_ticker,
             last_fetched, trade_count, trade_volume) = row
            
            probability = 50.0
            if yes_bid is not None and yes_ask is not None:
                mid_price = (yes_bid + yes_ask) / 2.0
                probability = round(mid_price, 1)
            elif yes_bid is not None:
                probability = round(float(yes_bid), 1)
            elif yes_ask is not None:
                probability = round(float(yes_ask), 1)
            
            spread = None
            if yes_bid is not None and yes_ask is not None:
                spread = round(yes_ask - yes_bid, 1)
            
            volume = int(db_volume) if db_volume else int(trade_volume)
            
            orders = []
            if trade_count > 0:
                order_cursor = conn.execute(
                    """
                    SELECT user_id, SUM(quantity) as total_qty, COUNT(*) as trade_count,
                           AVG(price) as avg_price, MAX(timestamp) as last_ts
                    FROM trades
                    WHERE market_id = ?
                    GROUP BY user_id
                    ORDER BY total_qty DESC
                    LIMIT 10
                    """,
                    (market_id,),
                )
                from datetime import datetime
                for idx, (user_id, qty, user_trade_count, user_avg_price, user_last_ts) in enumerate(order_cursor.fetchall()):
                    if user_id != "anonymous":
                        side = "buy" if user_avg_price and user_avg_price > 0.5 else "sell"
                        timestamp_ms = user_last_ts if user_last_ts else 0
                        time_str = datetime.fromtimestamp(timestamp_ms / 1000).strftime("%Y-%m-%d %H:%M") if timestamp_ms > 0 else "recently"
                        
                        orders.append({
                            "id": f"{market_id}-{user_id}-{idx}",
                            "owner": user_id,
                            "side": side,
                            "size": int(qty),
                            "tradeCount": int(user_trade_count),
                            "avgPrice": round(user_avg_price, 2) if user_avg_price else 0.5,
                            "createdAt": time_str,
                            "flag": "large" if qty > 100 else None,
                        })
            
            tags = []
            if status:
                tags.append(status)
            if liquidity and liquidity > 1000:
                tags.append("high-liquidity")
            if volume > 5000:
                tags.append("high-volume")
            if spread is not None and spread < 5:
                tags.append("tight-spread")
            if trade_count > 0:
                tags.append(f"{trade_count}-trades")
            
            last_fetched_str = None
            if last_fetched:
                from datetime import datetime
                last_fetched_str = datetime.fromtimestamp(last_fetched).isoformat() + "Z"
            
            markets.append({
                "id": market_id,
                "name": name[:80] if name else market_id,
                "probability": probability,
                "volume": volume,
                "liquidity": int(liquidity) if liquidity else 0,
                "spread": spread,
                "yesBid": round(yes_bid, 1) if yes_bid is not None else None,
                "yesAsk": round(yes_ask, 1) if yes_ask is not None else None,
                "noBid": round(no_bid, 1) if no_bid is not None else None,
                "noAsk": round(no_ask, 1) if no_ask is not None else None,
                "status": status or "unknown",
                "closeTime": close_time,
                "seriesTicker": series_ticker,
                "lastFetched": last_fetched_str,
                "tradeCount": trade_count,
                "description": name[:120] if name else f"Market: {market_id}",
                "tags": tags if tags else ["unknown"],
                "orders": orders,
            })
        return markets, total_count, last_sync
    except sqlite3.OperationalError as e:
        logger.error(f"Error fetching markets: {e}")
        return [], 0, None




def run_pipeline_task():
    """Background task to run the pipeline."""
    try:
        credentials = KalshiCredentials.from_env()
        env_name = get_kalshi_environment()
        environment = KalshiEnvironment.PROD if env_name == "PROD" else KalshiEnvironment.DEMO
        client = KalshiClient(
            credentials=credentials,
            environment=environment,
        )
        store = SQLiteStore(DB_PATH)
        config = PipelineConfig(market_limit=20, window_size=5)
        runner = PipelineRunner(client, store, config)
        runner.run(market_status="open", dry_run=False)
    except Exception as e:
        print(f"Pipeline error: {e}")


@app.get("/api/kalshi/dashboard-data")
async def get_dashboard_data() -> DashboardData:
    """Get aggregated dashboard data."""
    conn = get_db()
    
    market_count = count_table_rows(conn, "markets")
    trade_count = count_table_rows(conn, "trades")
    request_count = count_table_rows(conn, "request_metadata")
    raw_count = count_table_rows(conn, "raw_payload")
    
    pipeline_runs = [
        {
            "id": "last-run",
            "label": "Market ingestion",
            "status": "healthy" if market_count > 0 else "idle",
            "lastRun": "recently",
            "duration": "varies",
            "message": f"{market_count} markets, {trade_count} trades stored",
        }
    ]
    
    database_snapshots = [
        {
            "table": "markets",
            "rows": market_count,
            "anomalies": 0,
            "lastUpdated": "recently",
            "alertLevel": "info",
        },
        {
            "table": "trades",
            "rows": trade_count,
            "anomalies": 0,
            "lastUpdated": "recently",
            "alertLevel": "info",
        },
        {
            "table": "raw_payload",
            "rows": raw_count,
            "anomalies": 0,
            "lastUpdated": "recently",
        },
        {
            "table": "request_metadata",
            "rows": request_count,
            "anomalies": 0,
            "lastUpdated": "recently",
        },
    ]
    
    markets, _, _ = get_markets(conn, limit=10, sort_by="volume", sort_order="desc")
    conn.close()
    
    return DashboardData(
        pipelineRuns=pipeline_runs,
        databaseSnapshots=database_snapshots,
        markets=markets,
    )


@app.post("/api/pipelines")
async def trigger_pipeline(background_tasks: BackgroundTasks) -> PipelineRunResponse:
    """Trigger a new pipeline run in the background."""
    run_id = f"run-{int(time.time())}"
    background_tasks.add_task(run_pipeline_task)
    
    return PipelineRunResponse(
        status="queued",
        message="Pipeline run started in background",
        run_id=run_id,
    )


@app.get("/api/database/{table}")
async def query_table(
    table: str,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """Query a database table with pagination."""
    allowed_tables = ["markets", "trades", "raw_payload", "request_metadata"]
    if table not in allowed_tables:
        raise HTTPException(status_code=404, detail="Table not found")
    
    conn = get_db()
    
    try:
        cursor = conn.execute(f"SELECT * FROM {table} LIMIT ? OFFSET ?", (limit, offset))
        columns = [desc[0] for desc in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        count_cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
        total = count_cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "table": table,
            "rows": rows,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    except sqlite3.OperationalError as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/kalshi/candlesticks/{ticker}")
async def get_market_candlesticks(
    ticker: str,
    start_ts: int,
    end_ts: int,
    period_interval: int = 60,
) -> dict[str, Any]:
    """Get candlestick data for a specific market."""
    try:
        credentials = KalshiCredentials.from_env()
        env_name = get_kalshi_environment()
        environment = KalshiEnvironment.PROD if env_name == "PROD" else KalshiEnvironment.DEMO
        client = KalshiClient(
            credentials=credentials,
            environment=environment,
        )
        
        conn = get_db()
        cursor = conn.execute(
            "SELECT series_ticker FROM markets WHERE market_id = ? LIMIT 1",
            (ticker,),
        )
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0]:
            series_ticker = result[0]
        else:
            series_ticker = ticker.split("-")[0] if "-" in ticker else ticker
        
        if not series_ticker:
            raise HTTPException(
                status_code=404,
                detail=f"Cannot determine series_ticker for market {ticker}"
            )
        
        logger.info(
            f"Fetching candlesticks: series={series_ticker}, ticker={ticker}, "
            f"start={start_ts}, end={end_ts}, interval={period_interval}, env={env_name}"
        )
        
        try:
            response = client.get_market_candlesticks(
                series_ticker=series_ticker,
                ticker=ticker,
                start_ts=start_ts,
                end_ts=end_ts,
                period_interval=period_interval,
            )
            
            logger.info(f"Got {len(response.candlesticks)} candlesticks for {ticker}")
            
            return {
                "ticker": response.ticker,
                "candlesticks": [
                    {
                        "timestamp": c.end_period_ts,
                        "open": c.price.open if c.price else None,
                        "high": c.price.high if c.price else None,
                        "low": c.price.low if c.price else None,
                        "close": c.price.close if c.price else None,
                        "volume": c.volume,
                        "open_interest": c.open_interest,
                    }
                    for c in response.candlesticks
                ],
            }
        except Exception as api_error:
            logger.error(f"Candlestick API error for {ticker}: {api_error}")
            return {
                "ticker": ticker,
                "candlesticks": [],
                "error": str(api_error),
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/kalshi/markets")
async def get_markets_endpoint(
    limit: int = 10,
    offset: int = 0,
    sort_by: str = "volume",
    sort_order: str = "desc",
    status: str | None = None,
    search: str | None = None,
    min_volume: float | None = None,
    max_volume: float | None = None,
    min_liquidity: float | None = None,
    max_liquidity: float | None = None,
) -> MarketsResponse:
    """Get markets with filtering, sorting, and pagination."""
    conn = get_db()
    
    markets, total, last_sync = get_markets(
        conn=conn,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
        status=status,
        search=search,
        min_volume=min_volume,
        max_volume=max_volume,
        min_liquidity=min_liquidity,
        max_liquidity=max_liquidity,
    )
    
    conn.close()
    
    return MarketsResponse(
        markets=markets,
        total=total,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
        last_sync=last_sync,
    )


@app.post("/api/kalshi/markets/sync-all")
async def sync_all_markets_endpoint(
    background_tasks: BackgroundTasks,
    status: str | None = None,
) -> SyncAllResponse:
    """Trigger full market sync in background."""
    job_id = f"sync-{int(time.time())}"
    
    def sync_task():
        try:
            credentials = KalshiCredentials.from_env()
            env_name = get_kalshi_environment()
            environment = KalshiEnvironment.PROD if env_name == "PROD" else KalshiEnvironment.DEMO
            client = KalshiClient(
                credentials=credentials,
                environment=environment,
            )
            store = SQLiteStore(DB_PATH)
            runner = PipelineRunner(client, store)
            runner.sync_all_markets(status=status)
        except Exception as e:
            logger.error(f"Sync all markets failed: {e}")
    
    background_tasks.add_task(sync_task)
    
    return SyncAllResponse(
        status="queued",
        message=f"Full market sync started for status: {status or 'all'}",
        job_id=job_id,
    )


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
