# Kalsh

Kalshi anomaly detection pipeline with web dashboard.

## Setup

```bash
pip install -e ".[dev]"
```

Set up your Kalshi credentials in `.env`:
```
KALSHI_API_KEY=your_key
KALSHI_API_SECRET=your_secret
```

## Dashboard

Start both API and dashboard together:
```bash
make dev
```

Or start them separately:
```bash
# Terminal 1
make api

# Terminal 2
make dashboard-dev
```

Visit `http://localhost:3000` to view the dashboard.

## CLI Pipeline

Run the pipeline from the command line:
```bash
python scripts/run_pipeline.py --market-limit 20
```

## Development

Lint:
```bash
make lint
```

Test:
```bash
make test
```

