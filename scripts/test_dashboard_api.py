"""Test script to verify dashboard API returns correct data."""

import sqlite3
import json
from kalsh.api import get_recent_markets, get_db

def test_api_endpoint():
    """Test that the API endpoint returns correct market data."""
    conn = get_db()
    
    cursor = conn.execute("SELECT COUNT(*) FROM markets")
    market_count = cursor.fetchone()[0]
    print(f"Total markets in database: {market_count}")
    
    if market_count == 0:
        print("No markets in database. Run the pipeline first.")
        conn.close()
        return
    
    markets = get_recent_markets(conn, limit=10)
    conn.close()
    
    print(f"\nFetched {len(markets)} markets from API endpoint:")
    print("="*80)
    
    for i, market in enumerate(markets[:5], 1):
        print(f"\n{i}. {market['name']}")
        print(f"   ID: {market['id']}")
        print(f"   Probability: {market['probability']}%")
        print(f"   Volume: {market['volume']:,}")
        print(f"   Liquidity: {market.get('liquidity', 0):,}")
        print(f"   Spread: {market.get('spread', 'N/A')}")
        print(f"   Status: {market.get('status', 'unknown')}")
        print(f"   Yes Bid/Ask: {market.get('yesBid', 'N/A')} / {market.get('yesAsk', 'N/A')}")
        print(f"   Trades: {market.get('tradeCount', 0)}")
        print(f"   Top Traders: {len(market['orders'])}")
        print(f"   Tags: {', '.join(market['tags'])}")
    
    print("\n" + "="*80)
    print(f"\nSample JSON response (first market):")
    print(json.dumps(markets[0] if markets else {}, indent=2))

if __name__ == "__main__":
    test_api_endpoint()
