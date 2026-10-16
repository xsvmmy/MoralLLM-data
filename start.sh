#!/usr/bin/env bash
# start.sh — launch backend + frontend together
# Usage: ./start.sh
# Stop both: Ctrl+C

set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

# ── Backend ──────────────────────────────────────────────────────────────────
echo "Starting backend on http://localhost:8010 ..."
cd "$ROOT/backend"

if [ ! -f "venv/bin/activate" ]; then
  echo "(Re)creating Python venv..."
  rm -rf venv
  python3 -m venv venv
fi

source venv/bin/activate
pip install -q -r "$ROOT/requirements.txt"
uvicorn main:app --reload --port 8010 &
BACKEND_PID=$!
deactivate

# ── Frontend ─────────────────────────────────────────────────────────────────
echo "Starting frontend on http://localhost:3000 ..."
cd "$ROOT/frontend"

if [ ! -f "node_modules/.bin/vite" ]; then
  echo "Installing npm dependencies..."
  npm install
fi

npm run dev &
FRONTEND_PID=$!

# ── Cleanup on Ctrl+C ────────────────────────────────────────────────────────
trap "echo 'Stopping...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM

echo ""
echo "  Frontend: http://localhost:3000"
echo "  Backend:  http://localhost:8010"
echo "  Press Ctrl+C to stop both."
echo ""

wait
