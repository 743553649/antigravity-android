#!/usr/bin/env bash
# 02_r_java.sh - Generates R.java from Android resources using aapt.
set -euo pipefail

GEN_DIR="${1:-$BUILD_DIR/gen}"
MANIFEST="${2:-$APP_DIR/src/main/AndroidManifest.xml}"
RES_DIR="${3:-$APP_DIR/src/main/res}"
ANDROID_JAR="${4:-$TOOLS_DIR/android.jar}"

echo "[*] [02_r_java] Generating R.java..."
mkdir -p "$GEN_DIR"
aapt package -f -m \
    -J "$GEN_DIR" \
    -M "$MANIFEST" \
    -S "$RES_DIR" \
    -I "$ANDROID_JAR"

echo "[OK] [02_r_java] R.java generated in $GEN_DIR"
