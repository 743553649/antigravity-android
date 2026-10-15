#!/usr/bin/env bash
# 04_dex.sh - Converts compiled Java bytecode into classes.dex via D8/R8.
set -euo pipefail

DEX_DIR="${1:-$BUILD_DIR/dex}"
OBJ_DIR="${2:-$BUILD_DIR/obj}"
R8_JAR="${3:-$TOOLS_DIR/r8.jar}"
ANDROID_JAR="${4:-$TOOLS_DIR/android.jar}"
MIN_API="${5:-24}"

echo "[*] [04_dex] Running D8 dexer..."
mkdir -p "$DEX_DIR"

mapfile -d '' CLASS_FILES < <(find "$OBJ_DIR" -name '*.class' -print0)
[ "${#CLASS_FILES[@]}" -gt 0 ] || { echo "Error: no class files found under $OBJ_DIR" >&2; exit 1; }

java -cp "$R8_JAR" com.android.tools.r8.D8 \
    --output "$DEX_DIR" \
    --lib "$ANDROID_JAR" \
    --min-api "$MIN_API" \
    "${CLASS_FILES[@]}"

[ -f "$DEX_DIR/classes.dex" ] || { echo "Error: D8 did not produce classes.dex" >&2; exit 1; }
echo "[OK] [04_dex] Produced $(stat -c%s "$DEX_DIR/classes.dex") bytes classes.dex"
