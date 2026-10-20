#!/usr/bin/env bash
# 02_r_java.sh - Generates R.java from Android resources using aapt.
set -euo pipefail

GEN_DIR="${1:-$BUILD_DIR/gen}"
MANIFEST="${2:-$APP_DIR/src/main/AndroidManifest.xml}"
RES_DIR="${3:-$APP_DIR/src/main/res}"
ANDROID_JAR="${4:-$TOOLS_DIR/android.jar}"
BUILD_RES_DIR="${5:-${BUILD_DIR:-}/res}"

PKG=$(sed -n -E 's/.*package="([^"]+)".*/\1/p' "$MANIFEST" | head -n 1)

RES_ARGS=()
if [ -n "${BUILD_RES_DIR:-}" ] && [ -d "$BUILD_RES_DIR" ]; then
    RES_ARGS+=(-S "$BUILD_RES_DIR")
fi
RES_ARGS+=(-S "$RES_DIR" --auto-add-overlay)

echo "[*] [02_r_java] Generating R.java..."
mkdir -p "$GEN_DIR"
aapt package -f -m \
    -J "$GEN_DIR" \
    -M "$MANIFEST" \
    "${RES_ARGS[@]}" \
    -I "$ANDROID_JAR"

# Ensure com.agy.R is always generated for internal source code referencing com.agy.R
# If the manifest package is already com.agy, the first call already generated com.agy.R.
if [ "$PKG" != "com.agy" ]; then
    echo "[*] [02_r_java] Generating fallback com.agy.R for package $PKG..."
    aapt package -f -m \
        -J "$GEN_DIR" \
        -M "$MANIFEST" \
        "${RES_ARGS[@]}" \
        -I "$ANDROID_JAR" \
        --custom-package com.agy
fi

echo "[OK] [02_r_java] R.java generated in $GEN_DIR"
