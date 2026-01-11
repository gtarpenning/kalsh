#!/bin/bash
# Test script for the Kalsh API

API_URL="http://127.0.0.1:8000"

echo "Testing Kalsh API endpoints..."
echo

echo "1. Health check:"
curl -s "$API_URL/health" | python -m json.tool
echo

echo "2. Dashboard data:"
curl -s "$API_URL/api/kalshi/dashboard-data" | python -m json.tool | head -30
echo

echo "3. Query markets table:"
curl -s "$API_URL/api/database/markets?limit=2" | python -m json.tool
echo

echo "4. Query trades table:"
curl -s "$API_URL/api/database/trades?limit=2" | python -m json.tool
echo

echo "5. Trigger pipeline:"
curl -s -X POST "$API_URL/api/pipelines" | python -m json.tool
echo

echo "All tests complete!"
