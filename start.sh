#!/bin/bash
set -e

echo "[STARTUP] Starting environment server..."
uvicorn server.app:app --host 0.0.0.0 --port 7860 &
SERVER_PID=$!

echo "[STARTUP] Waiting for server to be healthy..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:7860/health > /dev/null 2>&1; then
        echo "[STARTUP] Server is healthy after ${i}s"
        break
    fi
    sleep 1
done

echo "[STARTUP] Running inference.py..."
python inference.py

echo "[STARTUP] inference.py complete. Keeping server alive..."
wait $SERVER_PID