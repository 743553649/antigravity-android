#!/usr/bin/env bash
# 06_package.sh - Packages Android resources, assets, and classes.dex into unaligned.apk.
set -euo pipefail

UNALIGNED_APK="${1:-$BUILD_DIR/unaligned.apk}"
MANIFEST="${2:-$APP_DIR/src/main/AndroidManifest.xml}"
RES_DIR="${3:-$APP_DIR/src/main/res}"
ANDROID_JAR="${4:-$TOOLS_DIR/android.jar}"
STAGE_ASSETS="${5:-$BUILD_DIR/staging/assets}"
DEX_FILE="${6:-$BUILD_DIR/dex/classes.dex}"

echo "[*] [06_package] Packaging base resources into unaligned APK..."
aapt package -f \
    -M "$MANIFEST" \
    -S "$RES_DIR" \
    -I "$ANDROID_JAR" \
    -F "$UNALIGNED_APK"

echo "[*] [06_package] Injecting classes.dex and assets into APK..."
python3 - "$UNALIGNED_APK" "$DEX_FILE" "$STAGE_ASSETS" <<'PY'
import sys, zipfile, os

apk_path = sys.argv[1]
dex_path = sys.argv[2]
assets_dir = sys.argv[3]

with zipfile.ZipFile(apk_path, "a", compression=zipfile.ZIP_DEFLATED) as z:
    z.write(dex_path, "classes.dex")
    if os.path.isdir(assets_dir):
        staging_parent = os.path.dirname(assets_dir)
        for root, dirs, files in os.walk(assets_dir):
            for f in files:
                full = os.path.join(root, f)
                rel = os.path.relpath(full, staging_parent)
                # Avoid recompressing already-compressed archives
                comp = zipfile.ZIP_STORED if f.endswith(('.gz', '.tgz', '.zip', '.png', '.jpg')) else zipfile.ZIP_DEFLATED
                z.write(full, rel, compress_type=comp)
PY

echo "[OK] [06_package] Created $(stat -c%s "$UNALIGNED_APK") bytes unaligned.apk"
