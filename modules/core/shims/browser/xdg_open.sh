#!/system/bin/sh
# AGY URL opener shim (xdg-open / open / sensible-browser).
# Dispatches URLs to Android Activity Manager & CoreProcessSupervisor.

unset LD_PRELOAD
unset LD_LIBRARY_PATH

URL="$1"
[ -z "$URL" ] && URL="$2"
[ -z "$URL" ] && exit 0

# Primary channel: output to stdout captured by CoreProcessSupervisor
echo "AGY_OPEN_URL=$URL"
echo "ANTIGRAVITY_OPEN_URL: $URL"

# Direct intent / broadcast fallback for terminal and standalone commands
if [ -x /system/bin/am ]; then
  /system/bin/am broadcast -a com.agy.ACTION_OPEN_URL -p com.agy --es url "$URL" >/dev/null 2>&1 || true
  /system/bin/am broadcast -a com.agy.ACTION_OPEN_URL -p com.agy.dev --es url "$URL" >/dev/null 2>&1 || true
  /system/bin/am start -a android.intent.action.VIEW -d "$URL" >/dev/null 2>&1 || true
fi

exit 0
