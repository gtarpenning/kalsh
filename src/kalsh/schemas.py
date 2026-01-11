"""Typed Pydantic schemas for Kalshi API responses.

All models are based on the official Kalshi API documentation:
https://docs.kalshi.com/api-reference/
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class MarketStatus(str, Enum):
    """Market status enum."""

    OPEN = "open"
    CLOSED = "closed"
    SETTLED = "settled"
    FINALIZED = "finalized"


class OrderSide(str, Enum):
    """Order side enum."""

    YES = "yes"
    NO = "no"


class OrderAction(str, Enum):
    """Order action enum."""

    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """Order type enum."""

    LIMIT = "limit"
    MARKET = "market"


class OrderStatus(str, Enum):
    """Order status enum."""

    RESTING = "resting"
    CANCELED = "canceled"
    EXECUTED = "executed"
    PENDING = "pending"


class SelfTradePreventionType(str, Enum):
    """Self trade prevention type enum."""

    TAKER_AT_CROSS = "taker_at_cross"
    CANCEL_RESTING = "cancel_resting"
    CANCEL_AGGRESSING = "cancel_aggressing"


class Market(BaseModel):
    """Market response from GET /trade-api/v2/markets."""

    ticker: str = Field(..., description="Market ticker (unique identifier)")
    title: str = Field(..., description="Human-readable market title")
    subtitle: str | None = Field(None, description="Market subtitle")
    status: str = Field(..., description="Market status: open, closed, settled, finalized")
    category: str | None = Field(None, description="Market category")
    
    # Pricing info (in cents, 0-100)
    yes_bid: int | None = Field(None, description="Current yes bid price in cents")
    yes_ask: int | None = Field(None, description="Current yes ask price in cents")
    no_bid: int | None = Field(None, description="Current no bid price in cents")
    no_ask: int | None = Field(None, description="Current no ask price in cents")
    last_price: int | None = Field(None, description="Last trade price in cents")
    
    # Volume and liquidity
    volume: int | None = Field(None, description="Total volume traded")
    volume_24h: int | None = Field(None, description="24-hour volume")
    liquidity: int | None = Field(None, description="Total liquidity available")
    open_interest: int | None = Field(None, description="Current open interest")
    
    # Timestamps
    open_time: datetime | None = Field(None, description="Market open timestamp")
    close_time: datetime | None = Field(None, description="Market close timestamp")
    expected_expiration_time: datetime | None = Field(None, description="Expected expiration")
    settlement_value: int | None = Field(None, description="Settlement value (0 or 100)")
    result: str | None = Field(None, description="Settlement result: yes or no")
    
    # Market metadata
    event_ticker: str | None = Field(None, description="Parent event ticker")
    series_ticker: str | None = Field(None, description="Parent series ticker")
    market_type: str | None = Field(None, description="Market type")
    strike: str | None = Field(None, description="Strike for binary markets")
    floor_strike: float | None = Field(None, description="Floor strike for ranged markets")
    cap_strike: float | None = Field(None, description="Cap strike for ranged markets")
    
    # Additional fields
    can_close_early: bool | None = Field(None, description="Whether market can close early")
    expiration_value: str | None = Field(None, description="Value used for expiration")
    functional_strike: str | None = Field(None, description="Functional strike value")
    
    model_config = ConfigDict(populate_by_name=True)


class MarketsResponse(BaseModel):
    """Response from GET /trade-api/v2/markets."""

    markets: list[Market]
    cursor: str | None = Field(None, description="Pagination cursor for next page")
    next_cursor: str | None = Field(None, description="Alternative cursor field")


class Trade(BaseModel):
    """Trade response from GET /trade-api/v2/markets/trades."""

    trade_id: str = Field(..., description="Unique trade identifier (UUID)")
    ticker: str = Field(..., description="Market ticker this trade belongs to")
    
    # Price info
    price: float = Field(..., description="Execution price as decimal (0.0-1.0)")
    yes_price: int = Field(..., description="Yes side price in cents")
    no_price: int = Field(..., description="No side price in cents")
    
    # Quantity
    count: int = Field(..., description="Number of contracts traded")
    
    # Taker info
    taker_side: str = Field(..., description="Side the taker took: yes or no")
    
    # Timestamp
    created_time: datetime = Field(..., description="Trade execution timestamp")
    
    # Optional fields (may not be available in public API)
    trade_type: str | None = Field(None, description="Type of trade")
    
    model_config = ConfigDict(populate_by_name=True)


class TradesResponse(BaseModel):
    """Response from GET /trade-api/v2/markets/trades."""

    trades: list[Trade]
    cursor: str | None = Field(None, description="Pagination cursor for next page")
    next_cursor: str | None = Field(None, description="Alternative cursor field")


class Order(BaseModel):
    """Order response from GET /trade-api/v2/portfolio/orders."""

    order_id: str = Field(..., description="Unique order identifier")
    user_id: str = Field(..., description="User who placed the order")
    client_order_id: str | None = Field(None, description="Client-provided order ID")
    ticker: str = Field(..., description="Market ticker")
    
    side: OrderSide = Field(..., description="Order side: yes or no")
    action: OrderAction = Field(..., description="Order action: buy or sell")
    type: OrderType = Field(..., description="Order type: limit or market")
    status: OrderStatus = Field(..., description="Order status")
    
    # Pricing (in cents)
    yes_price: int = Field(..., description="Yes price in cents")
    no_price: int = Field(..., description="No price in cents")
    yes_price_dollars: str | None = Field(None, description="Yes price in dollars (string)")
    no_price_dollars: str | None = Field(None, description="No price in dollars (string)")
    
    # Quantity
    fill_count: int = Field(..., description="Number of contracts filled")
    remaining_count: int = Field(..., description="Number of contracts remaining")
    initial_count: int = Field(..., description="Initial number of contracts")
    
    # Fees and costs
    taker_fees: int = Field(..., description="Taker fees in cents")
    maker_fees: int = Field(..., description="Maker fees in cents")
    taker_fill_cost: int = Field(..., description="Taker fill cost in cents")
    maker_fill_cost: int = Field(..., description="Maker fill cost in cents")
    taker_fees_dollars: str | None = Field(None, description="Taker fees in dollars")
    maker_fees_dollars: str | None = Field(None, description="Maker fees in dollars")
    taker_fill_cost_dollars: str | None = Field(None, description="Taker fill cost in dollars")
    maker_fill_cost_dollars: str | None = Field(None, description="Maker fill cost in dollars")
    
    # Queue and timing
    queue_position: int | None = Field(None, description="Position in order queue")
    expiration_time: datetime | None = Field(None, description="Order expiration time")
    created_time: datetime = Field(..., description="Order creation time")
    last_update_time: datetime = Field(..., description="Last update time")
    
    # Additional settings
    self_trade_prevention_type: SelfTradePreventionType | None = Field(
        None, description="Self-trade prevention strategy"
    )
    order_group_id: str | None = Field(None, description="Order group ID if part of a group")
    cancel_order_on_pause: bool | None = Field(None, description="Cancel on market pause")
    
    model_config = ConfigDict(populate_by_name=True)


class OrdersResponse(BaseModel):
    """Response from GET /trade-api/v2/portfolio/orders."""

    orders: list[Order]
    cursor: str | None = Field(None, description="Pagination cursor for next page")


class Balance(BaseModel):
    """Balance response from GET /trade-api/v2/portfolio/balance."""

    balance: int = Field(..., description="Available balance in cents")
    payout: int | None = Field(None, description="Pending payout in cents")
    
    model_config = ConfigDict(populate_by_name=True)


class ExchangeStatus(BaseModel):
    """Exchange status from GET /trade-api/v2/exchange/status."""

    exchange_active: bool = Field(..., description="Whether exchange is active")
    trading_active: bool = Field(..., description="Whether trading is active")
    
    model_config = ConfigDict(populate_by_name=True)


class Position(BaseModel):
    """Position response from GET /trade-api/v2/portfolio/positions."""

    ticker: str = Field(..., description="Market ticker")
    position: int = Field(..., description="Net position (positive = yes, negative = no)")
    market_exposure: int = Field(..., description="Market exposure in cents")
    total_traded: int = Field(..., description="Total contracts traded")
    resting_order_count: int = Field(..., description="Number of resting orders")
    
    model_config = ConfigDict(populate_by_name=True)


class PositionsResponse(BaseModel):
    """Response from GET /trade-api/v2/portfolio/positions."""

    positions: list[Position]
    cursor: str | None = Field(None, description="Pagination cursor for next page")


class Fill(BaseModel):
    """Fill response from GET /trade-api/v2/portfolio/fills."""

    fill_id: str = Field(..., description="Unique fill identifier")
    order_id: str = Field(..., description="Order that was filled")
    ticker: str = Field(..., description="Market ticker")
    side: OrderSide = Field(..., description="Fill side: yes or no")
    action: OrderAction = Field(..., description="Fill action: buy or sell")
    
    # Fill details
    count: int = Field(..., description="Number of contracts filled")
    yes_price: int = Field(..., description="Yes price in cents")
    no_price: int = Field(..., description="No price in cents")
    
    # Fees
    fees: int = Field(..., description="Fees paid in cents")
    is_taker: bool = Field(..., description="Whether this was a taker fill")
    
    # Timing
    created_time: datetime = Field(..., description="Fill timestamp")
    
    # Trade reference
    trade_id: str | None = Field(None, description="Associated trade ID")
    
    model_config = ConfigDict(populate_by_name=True)


class FillsResponse(BaseModel):
    """Response from GET /trade-api/v2/portfolio/fills."""

    fills: list[Fill]
    cursor: str | None = Field(None, description="Pagination cursor for next page")


class Event(BaseModel):
    """Event response from GET /trade-api/v2/events."""

    event_ticker: str = Field(..., description="Event ticker (unique identifier)")
    title: str = Field(..., description="Event title")
    subtitle: str | None = Field(None, description="Event subtitle")
    category: str = Field(..., description="Event category")
    series_ticker: str = Field(..., description="Parent series ticker")
    
    # Market info
    markets_count: int | None = Field(None, description="Number of markets in event")
    mutually_exclusive: bool | None = Field(None, description="Whether markets are mutually exclusive")
    
    model_config = ConfigDict(populate_by_name=True)


class EventsResponse(BaseModel):
    """Response from GET /trade-api/v2/events."""

    events: list[Event]
    cursor: str | None = Field(None, description="Pagination cursor for next page")


class Series(BaseModel):
    """Series response from GET /trade-api/v2/series."""

    series_ticker: str = Field(..., description="Series ticker (unique identifier)")
    title: str = Field(..., description="Series title")
    category: str = Field(..., description="Series category")
    frequency: str | None = Field(None, description="Event frequency")
    
    model_config = ConfigDict(populate_by_name=True)


class SeriesResponse(BaseModel):
    """Response from GET /trade-api/v2/series."""

    series: list[Series]
    cursor: str | None = Field(None, description="Pagination cursor for next page")


class CandlestickOHLC(BaseModel):
    """OHLC data for candlestick."""
    
    open: int | None = Field(None, description="Opening value in cents")
    open_dollars: str | None = Field(None, description="Opening value in dollars")
    low: int | None = Field(None, description="Low value in cents")
    low_dollars: str | None = Field(None, description="Low value in dollars")
    high: int | None = Field(None, description="High value in cents")
    high_dollars: str | None = Field(None, description="High value in dollars")
    close: int | None = Field(None, description="Closing value in cents")
    close_dollars: str | None = Field(None, description="Closing value in dollars")
    
    model_config = ConfigDict(populate_by_name=True)


class CandlestickPrice(BaseModel):
    """Extended price data for candlestick."""
    
    open: int | None = Field(None, description="Opening price in cents")
    open_dollars: str | None = Field(None, description="Opening price in dollars")
    low: int | None = Field(None, description="Low price in cents")
    low_dollars: str | None = Field(None, description="Low price in dollars")
    high: int | None = Field(None, description="High price in cents")
    high_dollars: str | None = Field(None, description="High price in dollars")
    close: int | None = Field(None, description="Closing price in cents")
    close_dollars: str | None = Field(None, description="Closing price in dollars")
    mean: int | None = Field(None, description="Mean price in cents")
    mean_dollars: str | None = Field(None, description="Mean price in dollars")
    previous: int | None = Field(None, description="Previous price in cents")
    previous_dollars: str | None = Field(None, description="Previous price in dollars")
    min: int | None = Field(None, description="Min price in cents")
    min_dollars: str | None = Field(None, description="Min price in dollars")
    max: int | None = Field(None, description="Max price in cents")
    max_dollars: str | None = Field(None, description="Max price in dollars")
    
    model_config = ConfigDict(populate_by_name=True)


class Candlestick(BaseModel):
    """Candlestick data point."""
    
    end_period_ts: int = Field(..., description="End of period timestamp")
    yes_bid: CandlestickOHLC | None = Field(None, description="Yes bid OHLC")
    yes_ask: CandlestickOHLC | None = Field(None, description="Yes ask OHLC")
    price: CandlestickPrice | None = Field(None, description="Price data")
    volume: int | None = Field(None, description="Volume in period")
    open_interest: int | None = Field(None, description="Open interest at end of period")
    
    model_config = ConfigDict(populate_by_name=True)


class CandlesticksResponse(BaseModel):
    """Response from GET /series/{series_ticker}/markets/{ticker}/candlesticks."""
    
    ticker: str = Field(..., description="Market ticker")
    candlesticks: list[Candlestick] = Field(..., description="Array of candlestick data")
    
    model_config = ConfigDict(populate_by_name=True)
