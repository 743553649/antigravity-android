#!/usr/bin/env bash
# run_all.sh - Runs syntax validation and all unit tests for modules/env.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== [1/2] Syntax Validation (Python & Shell) ===${NC}"

python3 -m compileall -q "$ENV_ROOT"
echo "  [OK] compileall: $ENV_ROOT"

find "$ENV_ROOT" -name "*.sh" | while read -r shfile; do
    bash -n "$shfile"
    echo "  [OK] bash -n: $(basename "$shfile")"
done

echo -e "\n${BLUE}=== [2/2] Running Python Unit Tests ===${NC}"
for test_file in "$SCRIPT_DIR"/test_*.py; do
    echo -e "${BLUE}--> Running $(basename "$test_file")...${NC}"
    python3 "$test_file"
done

echo -e "\n${GREEN}=== ALL ENV MODULE TESTS PASSED (Level 999999+1) ===${NC}\n"
