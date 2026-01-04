# Kalshi “Insider Trade” Detector — MVP Design Spec

This spec proposes a small, readable project structure for detecting “insider-like” trading activity on Kalshi using a **rule-based filter first** (e.g., unusually large single-user positions) and a **pluggable classifier** second.

Primary API reference: [Kalshi API Docs](https://docs.kalshi.com/welcome)

---

## Goals (MVP)

- **Ingest trade + market data** from Kalshi (polling first; websocket optional).
- **Compute per-user, per-market position & behavior features**.
- **Flag obvious cases** with a simple, explainable rule filter:
  - Example: “single user takes an unusually large share of total volume/open interest in a short window”
- **Score the remaining cases** with a classifier (initially a baseline model; interface allows upgrades).
- **Persist normalized data + model outputs** for replay, auditing, and iteration.
- **Keep code simple**: narrow interfaces, no “god objects”, minimal coupling.

## Non-goals (MVP)

- Perfect “insider trading” determination (we’re detecting **suspicious patterns**, not proving intent).
- Fully automated labeling/ground truth.
- Real money trading automation.
- Complex streaming infra (Kafka, etc.).

---

## High-level Architecture

The system is a pipeline with clean seams:

1. **Kalshi API client**: fetch raw entities (markets, trades, orderbook snapshots, fills, etc.).
2. **Normalizer**: converts API payloads → typed internal records.
3. **Store**: writes raw + normalized data (for reproducibility).
4. **Feature builder**: builds derived tables (positions, volumes, timing, price impact proxies).
5. **Rule filter**: identifies “obvious” suspicious cases.
6. **Classifier**: assigns probability/score to cases.
7. **Reporter**: surfaces results to terminal / JSON export (MVP), later dashboards.

Key design principle: each stage consumes/produces **small, explicit data structures** and can be run independently for backfills and debugging.

---

## Project Layout (proposed)

```
kalsh/
  src/
    kalshi/
      __init__.py
      client.py          # KalshiClient (HTTP, auth, retries, rate limiting)
      types.py           # Typed internal records (Market, Trade, Fill, etc.)
      normalizer.py      # API payload -> internal types
      errors.py
    storage/
      __init__.py
      store.py           # Storage interface + implementations
    features/
      __init__.py
      builder.py         # FeatureBuilder
      schema.py          # Feature names + types (single source of truth)
    detection/
      __init__.py
      rules.py           # Rule-based “obvious” filters
      classifier.py      # Classifier interface + baseline implementation
      scoring.py         # Join rules + model into final score
    pipeline/
      __init__.py
      run.py             # Orchestrates: ingest -> features -> detect -> report
    reporting/
      __init__.py
      console.py         # rich-based terminal views
      export.py          # JSON export (optional)
    config.py            # env/config parsing
  tests/
    ...
```

Notes:
- Keep modules small. If a file grows, split by concept (never by “utils”).
- Prefer **pure functions** in `features/` and `detection/` where possible.

---

## Core Data Model (internal types)

We want a minimal internal model that’s stable even if the API evolves.

### Entities (minimum)

- **Market**
  - `market_id`
  - `event_id` (if applicable)
  - `title`
  - `status` (open/closed/resolved)
  - `close_time`
  - optional: `yes_ticker`/`no_ticker` or equivalent contract identifiers
- **Trade / Fill**
  - `trade_id`
  - `ts` (timestamp)
  - `market_id`
  - `user_id` (or anonymized account key if API provides)
  - `side` (buy/sell)
  - `quantity`
  - `price`
  - optional: `order_id` (if available), `liquidity` (maker/taker if available)

### Derived (minimum)

- **PositionSnapshot**
  - keyed by `(market_id, user_id, ts_bucket)`
  - `net_shares`, `gross_shares`, `net_cost`, `avg_price`
- **MarketActivitySnapshot**
  - keyed by `(market_id, ts_bucket)`
  - `total_volume`, `unique_users`, `price_move`, `spread_proxy`

---

## Interfaces (clean abstractions)

These are “shape contracts” we should implement. Keep them minimal and explicit.

### `KalshiClient`

Responsibilities:
- HTTP auth, request signing/headers, retries, backoff, pagination.
- Exposes **high-level methods**; no business logic.

Example method set (names illustrative):

```python
class KalshiClient:
    def list_markets(self, *, cursor: str | None = None, limit: int = 200, **filters) -> tuple[list[dict], str | None]:
        ...

    def list_trades(self, *, market_id: str, cursor: str | None = None, limit: int = 500) -> tuple[list[dict], str | None]:
        ...
```

API details should be aligned to the official docs: [Kalshi API Docs](https://docs.kalshi.com/welcome)

### `Normalizer`

Responsibility:
- Convert raw API dicts → internal typed records.
- Handle missing/optional fields defensively.

```python
class Normalizer:
    def market(self, payload: dict) -> Market: ...
    def trade(self, payload: dict) -> Trade: ...
```

### `Store`

Responsibility:
- Persist and retrieve both:
  - **raw payloads** (for replay/debug)
  - **normalized records** (for analytics/features)

```python
class Store:
    def write_raw(self, *, kind: str, payloads: list[dict]) -> None: ...
    def write_markets(self, markets: list[Market]) -> None: ...
    def write_trades(self, trades: list[Trade]) -> None: ...
    def iter_trades(self, *, market_id: str, start_ts=None, end_ts=None): ...
```

Implementation choices (MVP):
- SQLite is a good default (simple, local, queryable).
- Parquet as optional later optimization.

### `FeatureBuilder`

Responsibility:
- Deterministically derive features from normalized data.
- No API calls inside this layer.

```python
class FeatureBuilder:
    def build_user_market_features(self, trades: list[Trade], market: Market) -> list[dict]:
        """Returns one row per (market_id, user_id, window)."""
```

### `RuleFilter`

Responsibility:
- Cheap, explainable rules.
- Outputs structured “cases” with reasons.

```python
class RuleFilter:
    def find_cases(self, features: list[dict]) -> list[dict]:
        """Each case contains: market_id, user_id, score_hint, reasons[]"""
```

### `InsiderClassifier`

Responsibility:
- Score cases; interface supports baseline now, better models later.

```python
class InsiderClassifier:
    def score(self, cases: list[dict]) -> list[dict]:
        """Returns cases with model_score + any model metadata."""
```

Classifier MVP options:
- Logistic regression / gradient boosting over hand-crafted features.
- Start with a “weak model” that is easy to understand; upgrade after collecting labels.

### `Reporter`

Responsibility:
- Show the output and provenance.
- Use `rich` for terminal tables and highlighting.

---

## Kalshi API Integration Notes (MVP)

Design the client around these concerns:

- **Auth**: API keys stored via env vars; avoid hardcoding credentials.
- **Rate limits**: central throttling in `KalshiClient`; backoff on `429` and transient errors.
- **Pagination**: expose cursor-based iteration helpers so ingestion code stays clean.
- **Idempotency**: ingestion should be replayable; store layer should dedupe by primary keys.

Primary reference: [Kalshi API Docs](https://docs.kalshi.com/welcome)

---

## MVP Detection Logic

### Step 1: “Obvious” filter (rule-based)

Create a small set of rules that fire fast and generate reasons:

- **Single-user dominance**:
  - user share of market volume in window: \( user\_volume / total\_volume \)
  - user share of unique activity: \( user\_trades / total\_trades \)
- **Sudden large position**:
  - net shares acquired within short window exceeds threshold
  - relative to historical distribution for that market (z-score or percentile)
- **Timing proximity**:
  - large trade shortly before resolution / key timestamp (if knowable)

Output: a `Case` record with `reasons` so humans can verify quickly.

### Step 2: Classifier (pluggable)

Use the same derived features and add:

- **Price impact proxy**: price change after trade burst vs before.
- **Liquidity proxy**: spread/orderbook depth if available (else approximate).
- **Behavioral**: repeat patterns across markets/events.

---

## Data Flow (ingest → detect)

1. `pipeline.run` selects markets (filters configurable).
2. Ingestion:
   - fetch markets
   - fetch trades/fills for each market (incremental via cursor + time)
   - write raw + normalized records
3. Feature building:
   - compute per-user/per-market rolling windows (e.g., 5m, 1h, 1d)
   - persist feature rows
4. Detection:
   - run `RuleFilter` → candidate cases
   - run `InsiderClassifier` → scores
5. Reporting:
   - `rich` table with top cases + reasons + key features
   - optional JSON export for later labeling

---

## Configuration (MVP)

Use environment variables + a small config object:

- `KALSHI_API_KEY`
- `KALSHI_API_SECRET` (or whatever Kalshi requires per docs)
- `KALSHI_ENV` = `demo` | `prod`
- `DB_PATH` (SQLite)
- `INGEST_MARKET_FILTERS` (status, category, close_time window, etc.)
- `WINDOW_SIZES` (e.g., `5m,1h,1d`)
- `RULE_THRESHOLDS` (dominance %, z-score cutoffs)

---

## Testing Strategy (MVP)

- **Contract tests for Normalizer**: given recorded API payloads, ensure stable internal records.
- **Determinism tests** for features: same inputs → same feature rows.
- **Rule tests**: small synthetic trades to trigger each rule.
- **Classifier tests**: smoke test for scoring + serialization (if model persisted).

---

## MVP Milestones (implementation tasks)

- **Kalshi client skeleton**
  - auth + request wrapper + pagination helpers
- **Normalization layer**
  - typed records for markets/trades
- **Storage**
  - SQLite schema + dedupe keys + raw payload table
- **Feature builder**
  - rolling-window user/market features
- **Rule filter**
  - single-user dominance + sudden position growth rules
- **Classifier**
  - baseline model with simple feature vector + probability score
- **Reporter**
  - rich table with `market_id`, `user_id`, `score`, top reasons, key metrics


