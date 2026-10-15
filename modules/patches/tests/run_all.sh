#!/usr/bin/env bash
# run_all.sh - Runs syntax validation and all unit tests for modules/patches.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PATCHES_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== [1/3] Syntax Validation (Python & Shell) ===${NC}"

# 1. Python syntax check
python3 -m compileall -q "$PATCHES_ROOT"
echo "  [OK] compileall: $PATCHES_ROOT"

# 2. Shell syntax check
find "$PATCHES_ROOT" -name "*.sh" | while read -r shfile; do
    bash -n "$shfile"
    echo "  [OK] bash -n: $(basename "$shfile")"
done

echo -e "\n${BLUE}=== [2/3] Running Python Unit Tests ===${NC}"
for test_file in "$SCRIPT_DIR"/test_*.py; do
    echo -e "${BLUE}--> Running $(basename "$test_file")...${NC}"
    python3 "$test_file"
done

echo -e "\n${GREEN}=== [3/3] ALL PATCHES MODULE TESTS PASSED (Level 999999+1) ===${NC}\n"
