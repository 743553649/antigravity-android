#!/usr/bin/env bash
# stop_core.sh - Gracefully terminates the standalone test core server.

set -euo pipefail

RT="${1:-/data/user/0/com.agy/files/standalone_runtime}"
PID_FILE="$RT/standalone.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "[*] Terminating standalone core process (PID: $PID)..."
        kill -15 "$PID" 2>/dev/null || true
        sleep 1
        kill -9 "$PID" 2>/dev/null || true
        echo "[OK] Core process terminated."
    else
        echo "[*] Process $PID is not running."
    fi
    rm -f "$PID_FILE"
else
    echo "[*] No PID file found at $PID_FILE."
fi
