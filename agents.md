## Agents Notes
- Keep modules tight; split by concept (no utils catch-alls).  
- Favor small, pure functions in detection/feature layers.  
- Follow testing strategy: contract tests for normalizer, determinism for features, targeted rule checks, classifier smoke tests.  
- Use `pytest` via `python -m pytest` for harness smoke tests.  
- Run `ruff check .` for lint safety and `ty check .` for types before merging.  
- Respect data flow: `kalshi_client → normalizer → store → features → detection → reporter`.  
- Store Kalshi API keys/env in config, avoid hardcoding.  
- Leverage `rich` for human-friendly reporting.  
- `KalshiClient` wraps RSA-signed requests, retries, pagination, and rate-limit enforcement over markets/trades/exchange/balance endpoints.  
- `KalshiIngestor` normalizes markets/trades, writes raw payloads plus structured rows into `SQLiteStore`, which dedups raw payloads and exposes deterministic trade iteration.  
- `rules.FeatureBuilder` builds sliding windows of trades per market and `RuleFilter` flags dominance/sudden-growth cases for large users.

