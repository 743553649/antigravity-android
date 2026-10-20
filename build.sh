#!/usr/bin/env bash
# build.sh - Convenient root wrapper for Antigravity APK builder.
# Usage:
#   bash build.sh             # Build release edition with bypass (dist/antigravity.apk)
#   bash build.sh --no-bypass # Build release edition without bypass (dist/antigravity-nobypass.apk)
#   bash build.sh --dev       # Build dev edition (dist/antigravity-dev.apk)
#   bash build.sh --fast      # Fast uncompressed assets iteration

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$SCRIPT_DIR/modules/builder/build_apk.sh" "$@"
