#!/usr/bin/env bash
# build_apk.sh - Master orchestrator for building, dexing, packaging, and signing Antigravity APK.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
export BUILD_DIR="$PROJECT_ROOT/build"
export DIST_DIR="$PROJECT_ROOT/dist"
export APP_DIR="$PROJECT_ROOT/app"
export TOOLS_DIR="$PROJECT_ROOT/tools"

export PATH="/data/user/0/com.agy.dev/files/usr/bin:/data/user/0/com.agy/files/usr/bin:$PATH"
if [ -d "/data/user/0/com.agy.dev/files" ] && [ -w "/data/user/0/com.agy.dev/files" ]; then
    export HOME="/data/user/0/com.agy.dev/files"
else
    export HOME="/data/user/0/com.agy/files"
fi
export LANG=C.UTF-8
export LC_ALL=C.UTF-8

export FAST_BUILD=0
export DEV_MODE=0

for arg in "$@"; do
    if [ "$arg" = "--fast" ]; then
        export FAST_BUILD=1
    elif [ "$arg" = "--dev" ] || [ "$arg" = "-d" ]; then
        export DEV_MODE=1
    fi
done

if [ "$DEV_MODE" = "1" ]; then
    OUT_APK="$DIST_DIR/agy-dev.apk"
    EDITION_LABEL="DEV EDITION (com.agy.dev, port 45158, debuggable)"
else
    OUT_APK="$DIST_DIR/agy.apk"
    EDITION_LABEL="RELEASE EDITION (com.agy, port 45157)"
fi

echo "============================================================"
echo "  ANTIGRAVITY V2 APK BUILD PIPELINE"
echo "  $EDITION_LABEL"
if [ "$FAST_BUILD" = "1" ]; then
    echo "  [MODE: FAST ITERATION (UNCOMPRESSED ASSETS & CACHE)]"
fi
echo "============================================================"

# Check host tools
for tool in python3 aapt javac java apksigner; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "[ERROR] Missing required build tool: $tool" >&2
        exit 1
    fi
done

# Clean previous build artifacts
echo "[*] Cleaning build directories..."
rm -rf "$BUILD_DIR/gen" "$BUILD_DIR/obj" "$BUILD_DIR/dex" "$BUILD_DIR/staging" \
       "$BUILD_DIR/unaligned.apk" "$BUILD_DIR/aligned.apk"
mkdir -p "$BUILD_DIR/gen" "$BUILD_DIR/obj" "$BUILD_DIR/dex" "$BUILD_DIR/staging" "$DIST_DIR"

# Phase 01: Config Generation (creates BuildConfig.java, gen.xml, and build/AndroidManifest.xml)
echo -e "\n>>> [1/8] Generating Configs..."
python3 "$SCRIPT_DIR/01_gen_config.py" "$BUILD_DIR"

TARGET_MANIFEST="$BUILD_DIR/AndroidManifest.xml"

# Phase 02: Generate R.java
echo -e "\n>>> [2/8] Generating R.java..."
bash "$SCRIPT_DIR/02_r_java.sh" "$BUILD_DIR/gen" "$TARGET_MANIFEST" "$APP_DIR/src/main/res" "$TOOLS_DIR/android.jar"

# Phase 03: Compile Java Sources
echo -e "\n>>> [3/8] Compiling Java Sources..."
bash "$SCRIPT_DIR/03_compile_java.sh" "$BUILD_DIR/obj" "$BUILD_DIR/gen" "$APP_DIR/src/main/java" "$TOOLS_DIR/android.jar"

# Phase 04: D8 Dexing
echo -e "\n>>> [4/8] Converting Bytecode to classes.dex (D8)..."
bash "$SCRIPT_DIR/04_dex.sh" "$BUILD_DIR/dex" "$BUILD_DIR/obj" "$TOOLS_DIR/r8.jar" "$TOOLS_DIR/android.jar" 24

# Phase 05: Stage Assets
echo -e "\n>>> [5/8] Staging Runtime and Web Assets..."
python3 "$SCRIPT_DIR/05_stage_assets.py" "$BUILD_DIR/staging"

# Phase 06: Package Unaligned APK
echo -e "\n>>> [6/8] Packaging Unaligned APK..."
bash "$SCRIPT_DIR/06_package.sh" "$BUILD_DIR/unaligned.apk" "$TARGET_MANIFEST" "$APP_DIR/src/main/res" "$TOOLS_DIR/android.jar" "$BUILD_DIR/staging/assets" "$BUILD_DIR/dex/classes.dex"

# Phase 07: ZipAlign
echo -e "\n>>> [7/8] ZipAligning APK..."
python3 "$SCRIPT_DIR/align.py" "$BUILD_DIR/unaligned.apk" "$BUILD_DIR/aligned.apk" 4

# Phase 08: Sign and Verify APK
echo -e "\n>>> [8/8] Signing and Verifying APK..."
bash "$SCRIPT_DIR/08_sign.sh" "$BUILD_DIR/aligned.apk" "$OUT_APK" "$TOOLS_DIR/debug.keystore"
bash "$SCRIPT_DIR/09_verify.sh" "$OUT_APK"

echo "============================================================"
echo "  BUILD SUCCESSFUL! APK CREATED:"
echo "  $OUT_APK ($(stat -c%s "$OUT_APK") bytes)"
echo "============================================================"
