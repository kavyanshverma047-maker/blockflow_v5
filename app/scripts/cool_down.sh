#!/bin/bash
echo "🧊 Cooling down Blockflow (stop keep-alive + shutdown remote admin)..."
# kill any local keep_alive.py started in background
pkill -f keep_alive.py || true

BACKEND_URL="${BACKEND_URL:-https://blockflow-backend.onrender.com}"
AUTH_TOKEN="${BLOCKFLOW_KEY:-b04280b0e6ef46daa5b6a470c62b8175}"

# call the shutdown admin route (if implemented)
curl -s -X POST "$BACKEND_URL/api/admin/shutdown" -H "Authorization: Bearer $AUTH_TOKEN" > /dev/null || true
echo "✅ Demo mode safely shut down."
