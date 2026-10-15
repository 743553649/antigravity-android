#!/usr/bin/env bash
# start_core.sh - Launches the standalone Antigravity core with I/O bus integration.

set -euo pipefail

RUNNER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULES_DIR="$(cd "$RUNNER_DIR/.." && pwd)"

RT="${1:-/data/user/0/com.agy/files/standalone_runtime}"
PORT="${2:-45159}"
CSRF_TOKEN="test-csrf-token-12345"

LOADER="$RT/bin/libloader.so"
[ -f "$LOADER" ] || LOADER="$RT/bin/ld-linux-aarch64.so.1"
CORE="$RT/bin/liblanguage_server.so"
[ -f "$CORE" ] || CORE="$RT/bin/language_server"
LSE_COMPAT="$RT/lib/liblse_compat.so"

[ -f "$LOADER" ] || { echo "[ERROR] Loader missing: $LOADER"; exit 1; }
[ -f "$CORE" ]   || { echo "[ERROR] Core binary missing: $CORE"; exit 1; }

APP_ID="${AGY_APPLICATION_ID:-com.agy}"
APP_BASE="/data/user/0/$APP_ID"
export HOME="${HOME:-$APP_BASE/files}"
export TMPDIR="${TMPDIR:-$APP_BASE/cache}"
export SSL_CERT_FILE="$RT/certs/ca-certificates.crt"
export PATH="$RT/bin:${PREFIX:-$HOME/usr}/bin:$PATH"
export SHELL="$RT/bin/bash"
export LANG="C.UTF-8"
export LC_ALL="C.UTF-8"
export GODEBUG="netdns=go"
export ANTIGRAVITY_VSCODE_HOST="1"
export BROWSER="$RT/bin/xdg-open"

# Bionic LD_LIBRARY_PATH for host python3/tools
export LD_LIBRARY_PATH="${PREFIX:-$HOME/usr}/lib"
unset LD_PRELOAD

CMD=(
    "$LOADER"
    --library-path "$RT/lib"
)

if [ -f "$LSE_COMPAT" ]; then
    CMD+=(--preload "$LSE_COMPAT")
fi

CMD+=(
    "$CORE"
    --standalone
    --override_ide_name "antigravity"
    --subclient_type "hub"
    --override_ide_version "2.11.0"
    --override_user_agent_name "antigravity"
    --https_server_port "$PORT"
    --csrf_token "$CSRF_TOKEN"
    --app_data_dir "antigravity-app-standalone"
    --enable_sidecars
)

echo "[*] Launching core server on port $PORT..."
echo "[*] Connecting stdout/stderr to modules/io stream splitter..."

PID_FILE="$RT/standalone.pid"
LOG_FILE="$RT/core_output.log"

# Launch process with stream_splitter in background
(
    "${CMD[@]}" 2>&1 \
        | python3 "$MODULES_DIR/io/interceptors/stream_splitter.py"
) > "$LOG_FILE" 2>&1 &

SERVER_PID=$!
echo "$SERVER_PID" > "$PID_FILE"
echo "[OK] Core process started with PID: $SERVER_PID"
echo "[*] Log stream: $LOG_FILE"
