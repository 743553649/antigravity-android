#!/usr/bin/env bash
# 03_compile_java.sh - Compiles Java sources and generated classes.
set -euo pipefail

OBJ_DIR="${1:-$BUILD_DIR/obj}"
GEN_DIR="${2:-$BUILD_DIR/gen}"
SRC_DIR="${3:-$APP_DIR/src/main/java}"
ANDROID_JAR="${4:-$TOOLS_DIR/android.jar}"

echo "[*] [03_compile_java] Compiling Java sources..."
mkdir -p "$OBJ_DIR"

BUILD_DIR="${BUILD_DIR:-$(dirname "$OBJ_DIR")}"
ARG_FILE="$BUILD_DIR/java_sources.txt"

JAVA_COUNT=$(find "$SRC_DIR" -name '*.java' | wc -l)
GEN_COUNT=$(find "$GEN_DIR" -name '*.java' | wc -l)

[ "$JAVA_COUNT" -gt 0 ] || { echo "Error: no java sources found under $SRC_DIR" >&2; exit 1; }
[ "$GEN_COUNT" -gt 0 ] || { echo "Error: no generated sources found under $GEN_DIR" >&2; exit 1; }

mkdir -p "$BUILD_DIR"
find "$SRC_DIR" "$GEN_DIR" -name '*.java' | sed 's/.*/"&"/' > "$ARG_FILE"

javac -encoding UTF-8 -J-Dfile.encoding=UTF-8 \
    -source 1.8 -target 1.8 \
    -d "$OBJ_DIR" \
    -cp "$ANDROID_JAR" \
    "@$BUILD_DIR/java_sources.txt"

echo "[OK] [03_compile_java] Compiled $(find "$OBJ_DIR" -name '*.class' | wc -l) classes into $OBJ_DIR"
