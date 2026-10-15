#!/usr/bin/env bash
# test_e2e.sh - Comprehensive end-to-end integration test of Core + Patches + I/O.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOME_DIR="${HOME:-/data/user/0/${AGY_APPLICATION_ID:-com.agy}/files}"
RT="${HOME_DIR}/standalone_runtime"
PORT="45159"

GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== STEP 1: Preparing and Assembling Patched Runtime ===${NC}"
python3 "$SCRIPT_DIR/prepare_runtime.py" "$RT"

echo -e "\n${BLUE}=== STEP 2: Starting Standalone Core Server with I/O Bus ===${NC}"
bash "$SCRIPT_DIR/start_core.sh" "$RT" "$PORT"

echo -e "\n${BLUE}=== STEP 3: Probing HTTP / LSP Server on Port $PORT ===${NC}"
if python3 "$SCRIPT_DIR/probe_server.py" "$PORT" 40; then
    echo -e "${GREEN}[SUCCESS] Standalone Core is UP and accepting requests!${NC}"
else
    echo -e "${RED}[FAILURE] Server failed to respond! Dumping log:${NC}"
    cat "$RT/core_output.log" 2>/dev/null || true
    bash "$SCRIPT_DIR/stop_core.sh" "$RT"
    exit 1
fi

echo -e "\n${BLUE}=== STEP 4: Inspecting Live Core Log Stream ===${NC}"
head -n 25 "$RT/core_output.log"

echo -e "\n${BLUE}=== STEP 5: Gracefully Stopping Test Server ===${NC}"
bash "$SCRIPT_DIR/stop_core.sh" "$RT"

echo -e "\n${GREEN}============================================================${NC}"
echo -e "${GREEN}  END-TO-END VALIDATION PASSED (Core + Patches + I/O OK!)   ${NC}"
echo -e "${GREEN}============================================================${NC}\n"
