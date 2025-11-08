#!/bin/bash
echo "🚀 Warming up Blockflow Backend..."

# Use existing env vars or defaults
BACKEND_URL="${BACKEND_URL:-https://blockflow-backend.onrender.com}"
BLOCKFLOW_KEY="${BLOCKFLOW_KEY:-your_secret_token_here}"

# Make silent warmup calls
curl -s "$BACKEND_URL/api/health" > /dev/null || true
curl -s "$BACKEND_URL/api/trades" > /dev/null || true
curl -s "$BACKEND_URL/api/dashboard-summary" > /dev/null || true
curl -s -X POST "$BACKEND_URL/api/admin/ignite" -H "Authorization: Bearer $BLOCKFLOW_KEY" > /dev/null || true

echo "✅ Backend warmed and live feed ignited."
