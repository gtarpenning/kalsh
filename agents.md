## Agents Notes
- Keep modules tight; split by concept (no utils catch-alls).  
- Favor small, pure functions in detection/feature layers.  
- Follow testing strategy: contract tests for normalizer, determinism for features, targeted rule checks, classifier smoke tests.  
- Use `pytest` via `python -m pytest` for harness smoke tests.  
- Run `ruff check .` for lint safety and `ty check .` for types before merging.  
- Respect data flow: `kalshi_client → normalizer → store → features → detection → reporter`.  
- Store Kalshi API keys/env in config, avoid hardcoding.  
- Leverage `rich` for human-friendly reporting.  

