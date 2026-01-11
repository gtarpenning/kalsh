#!/usr/bin/env python3
"""Example demonstrating typed Kalshi API access with Pydantic schemas.

This script shows how the new typed schemas provide better autocomplete,
type checking, and validation when working with Kalshi API responses.
"""

from kalsh import KalshiClient, KalshiCredentials, KalshiEnvironment


def main():
    """Demonstrate typed API usage."""
    credentials = KalshiCredentials.from_env()
    
    client = KalshiClient(
        credentials=credentials,
        environment=KalshiEnvironment.DEMO,
    )
    
    # Get exchange status (now returns typed ExchangeStatus object)
    status = client.get_exchange_status()
    print(f"Exchange Active: {status.exchange_active}")
    print(f"Trading Active: {status.trading_active}")
    
    # Get balance (now returns typed Balance object)
    balance = client.get_balance()
    print(f"\nBalance: ${balance.balance / 100:.2f}")
    if balance.payout:
        print(f"Pending Payout: ${balance.payout / 100:.2f}")
    
    # List markets (now returns typed MarketsResponse)
    markets_response = client.list_markets(status="open", per_page=5)
    
    print(f"\n{'='*60}")
    print("Top 5 Open Markets")
    print(f"{'='*60}\n")
    
    for market in markets_response.markets:
        # Type-safe access with autocomplete in your IDE!
        print(f"Ticker: {market.ticker}")
        print(f"Title: {market.title}")
        
        if market.yes_bid and market.yes_ask:
            spread = market.yes_ask - market.yes_bid
            print(f"Prices: Yes {market.yes_bid}¢ / {market.yes_ask}¢ (spread: {spread}¢)")
        
        if market.volume:
            print(f"Volume: {market.volume:,} contracts")
        
        if market.open_interest:
            print(f"Open Interest: {market.open_interest:,}")
        
        # Timestamps are properly typed as datetime objects
        if market.close_time:
            print(f"Closes: {market.close_time.isoformat()}")
        
        print()
    
    # List trades for first market (if available)
    if markets_response.markets:
        first_ticker = markets_response.markets[0].ticker
        print(f"{'='*60}")
        print(f"Recent Trades for {first_ticker}")
        print(f"{'='*60}\n")
        
        trades_response = client.list_trades(ticker=first_ticker, limit=5)
        
        for trade in trades_response.trades:
            # Type-safe trade access
            print(f"Trade ID: {trade.trade_id}")
            print(f"Price: ${trade.price:.2f} ({trade.yes_price}¢ yes / {trade.no_price}¢ no)")
            print(f"Contracts: {trade.count}")
            print(f"Taker Side: {trade.taker_side}")
            print(f"Time: {trade.created_time.isoformat()}")
            print()


if __name__ == "__main__":
    main()
