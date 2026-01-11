# Dashboard Backend Integration

## Overview

The Kalsh dashboard is now fully integrated with a Python FastAPI backend that serves real data from the SQLite database.

## Architecture

```
┌─────────────────┐      HTTP      ┌──────────────────┐
│  Next.js        │ ─────────────> │  FastAPI         │
│  Dashboard      │                │  Backend         │
│  (port 3000)    │ <───────────── │  (port 8000)     │
└─────────────────┘                └──────────────────┘
                                            │
                                            │ SQLite
                                            ▼
                                   ┌──────────────────┐
                                   │  kalshi_pipeline │
                                   │  .db             │
                                   └──────────────────┘
```

## API Endpoints

### `GET /api/kalshi/dashboard-data`
Returns aggregated dashboard data including:
- Pipeline run status
- Database table snapshots (row counts)
- Recent markets with orders

### `POST /api/pipelines`
Triggers a new pipeline run in the background. Returns immediately with a run ID.

### `GET /api/database/{table}`
Query any database table with pagination:
- `markets` - Market metadata
- `trades` - Trade records
- `raw_payload` - Raw API responses
- `request_metadata` - API request logs

Query parameters:
- `limit` - Number of rows (default: 100)
- `offset` - Pagination offset (default: 0)

### `GET /health`
Health check endpoint

## Setup

1. **Install dependencies:**
   ```bash
   pip install -e .
   cd dashboard && npm install
   ```

2. **Configure Kalshi credentials in `.env`:**
   ```
   KALSHI_API_KEY=your_key
   KALSHI_API_SECRET=your_secret
   ```

3. **Start both API and dashboard:**
   ```bash
   make dev
   ```
   
   This starts both servers together. Press Ctrl+C to stop both.
   
   Alternatively, run them separately:
   ```bash
   # Terminal 1
   make api
   
   # Terminal 2
   make dashboard-dev
   ```

4. **Visit:** `http://localhost:3000`

## Testing

Run the API test script:
```bash
./scripts/test_api.sh
```

Or test individual endpoints:
```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/kalshi/dashboard-data
curl http://127.0.0.1:8000/api/database/markets?limit=5
curl -X POST http://127.0.0.1:8000/api/pipelines
```

## Features

### Real-time Data
- Dashboard fetches live data from SQLite via the API
- Refresh button updates all data
- Pipeline runs update the database in the background

### Pipeline Control
- Click "Run pipeline" to trigger ingestion
- Pipeline runs asynchronously (non-blocking)
- Results appear in database after completion

### Database Viewer
- Shows row counts for all tables
- Real-time updates on refresh
- Displays anomaly counts (when detection is implemented)

### Market Explorer
- Browse markets from the database
- Search by name, description, or tags
- View aggregated order data per market

## Simplifications Made

1. **Removed Next.js API routes** - Dashboard calls Python API directly
2. **Single database** - All data in `kalshi_pipeline.db`
3. **Background tasks** - Pipeline runs don't block API responses
4. **Simple CORS** - Allows localhost:3000 to call localhost:8000
5. **Minimal error handling** - Returns standard HTTP status codes

## Configuration

The dashboard reads the API URL from environment variables:
```
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

This is set in `dashboard/.env.local` (gitignored).

## Future Enhancements

- Add WebSocket support for real-time pipeline status
- Store pipeline run history in database
- Add authentication/authorization
- Implement anomaly detection visualization
- Add filtering and sorting to database queries
