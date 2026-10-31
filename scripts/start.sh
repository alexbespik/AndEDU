#!/bin/bash
# One-command boot for SciEdu Studio

cd "$(dirname "$0")/.."

echo "⚡ Starting SciEdu Studio Backend API on port 8090..."
if [ -f "~/AndEDU/AndEdu/bin/python" ]; then
    ~/AndEDU/AndEdu/bin/python server.py &
else
    python3 server.py &
fi
BACKEND_PID=$!

echo "⚡ Starting SciEdu Studio Vite Frontend on port 5173..."
npx vite --port 5173 &
FRONTEND_PID=$!

sleep 1
echo "🚀 SciEdu Studio is live at: http://localhost:5173"
open "http://localhost:5173" 2>/dev/null || true

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT SIGTERM
wait
