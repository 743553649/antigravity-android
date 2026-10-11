#!/usr/bin/env bash
# build.sh - compile liblse_compat.so targeting baseline ARMv8.0-A
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CC="${CC:-clang}"
CFLAGS="${CFLAGS:--march=armv8-a -moutline-atomics -O2 -Wall -fPIC -shared}"

"$CC" $CFLAGS "$DIR/liblse_compat.c" -o "$DIR/liblse_compat.so"
echo "Built: $DIR/liblse_compat.so"
