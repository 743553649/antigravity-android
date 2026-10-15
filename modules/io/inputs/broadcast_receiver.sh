#!/system/bin/sh
# broadcast_receiver.sh - Translates Android Intent extras into an Antigravity event envelope.
# Usage: broadcast_receiver.sh <action> <extra_json_or_msg> [destination_fifo]

ACTION="${1:-com.agy.ACTION_DEFAULT}"
PAYLOAD="${2:-{}}"
FIFO="${3:-/data/user/0/com.agy/files/runtime/agy_bus.pipe}"

# Format as JSON envelope
NOW_MS=$(date +%s%3N 2>/dev/null || date +%s)
JSON="{\"event\":\"android.intent.$ACTION\",\"timestamp\":$NOW_MS,\"source\":\"android:am\",\"data\":{\"raw\":\"$PAYLOAD\"}}"

if [ -p "$FIFO" ]; then
    echo "$JSON" > "$FIFO"
else
    echo "$JSON"
fi
