#!/usr/bin/env bash
# 08_sign.sh - Signs the aligned APK using apksigner and debug.keystore.
set -euo pipefail

ALIGNED_APK="${1:-$BUILD_DIR/aligned.apk}"
OUT_APK="${2:-$DIST_DIR/antigravity.apk}"
KEYSTORE="${3:-$TOOLS_DIR/debug.keystore}"
KEY_ALIAS="${4:-androiddebugkey}"
KEY_PASS="${5:-android}"
STORE_PASS="${6:-android}"

echo "[*] [08_sign] Signing APK with debug.keystore..."
mkdir -p "$(dirname "$OUT_APK")"

apksigner sign \
    --ks "$KEYSTORE" \
    --ks-key-alias "$KEY_ALIAS" \
    --ks-pass "pass:$STORE_PASS" \
    --key-pass "pass:$KEY_PASS" \
    --out "$OUT_APK" \
    "$ALIGNED_APK"

echo "[OK] [08_sign] Signed APK created: $OUT_APK ($(stat -c%s "$OUT_APK") bytes)"
