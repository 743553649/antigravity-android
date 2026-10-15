#!/usr/bin/env bash
# run_all.sh - Runs syntax validation and tests for modules/builder.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILDER_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== [1/2] Syntax Validation (Python & Shell) ===${NC}"
python3 -m compileall -q "$BUILDER_DIR"
echo "  [OK] compileall: $BUILDER_DIR"

find "$BUILDER_DIR" -name "*.sh" | while read -r shfile; do
    bash -n "$shfile"
    echo "  [OK] bash -n: $(basename "$shfile")"
done

echo -e "\n${BLUE}=== [2/2] Running Python Unit Tests ===${NC}"
for test_file in "$SCRIPT_DIR"/test_*.py; do
    echo -e "${BLUE}--> Running $(basename "$test_file")...${NC}"
    python3 "$test_file"
done

echo -e "\n${GREEN}=== ALL BUILDER MODULE TESTS PASSED ===${NC}\n"
