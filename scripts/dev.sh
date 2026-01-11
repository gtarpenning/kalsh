#!/bin/bash
# Start both API and dashboard together

set -e

echo "🚀 Starting Kalsh development environment..."
echo ""

# Trap Ctrl+C to kill both processes
trap 'echo ""; echo "🛑 Shutting down..."; kill $(jobs -p) 2>/dev/null; exit' INT TERM

# Start API server
echo "📡 Starting API server on http://127.0.0.1:8000"
python scripts/run_api.py &
API_PID=$!

# Wait for API to be ready
sleep 2

# Start dashboard
echo "🎨 Starting dashboard on http://localhost:3000"
echo ""
cd dashboard && npm run dev &
DASHBOARD_PID=$!

# Wait for both processes
wait
