#!/usr/bin/env bash
# ==============================================================================
# TEMPLATE: Create a new custom Input endpoint in 3 easy steps!
# 1. Read or receive data from your custom source (sensor, webhook, timer, MQTT).
# 2. Format it as an Event Envelope JSON (event, timestamp, source, data).
# 3. Output to the AGY bus FIFO pipe or stdout.
# ==============================================================================

FIFO_PATH="${AGY_BUS_FIFO:-/data/user/0/com.agy/files/runtime/agy_bus.pipe}"

# Step 1: Obtain your custom input
INPUT_DATA="$1"
[ -z "$INPUT_DATA" ] && INPUT_DATA="default_payload"

# Step 2: Build JSON envelope
TIMESTAMP=$(date +%s%3N 2>/dev/null || date +%s)
JSON_EVENT="{\"event\":\"custom.my_event\",\"timestamp\":$TIMESTAMP,\"source\":\"input:custom\",\"data\":{\"value\":\"$INPUT_DATA\"}}"

# Step 3: Send to bus
if [ -p "$FIFO_PATH" ]; then
    echo "$JSON_EVENT" > "$FIFO_PATH"
else
    echo "$JSON_EVENT"
fi
