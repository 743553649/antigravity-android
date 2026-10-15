#!/system/bin/sh
# AGY browser delegator: delegates to xdg-open in the same directory.
exec "$(dirname "$0")/xdg-open" "$@"
