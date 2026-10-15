#!/usr/bin/env bash
# ==============================================================================
# TEMPLATE: Create a new custom Output endpoint in 3 easy steps!
# 1. Read JSON event envelope from stdin.
# 2. Extract fields (e.g. event, source, data fields).
# 3. Deliver to your custom destination (Telegram, Webhook, Cloud Log, Sound).
# ==============================================================================

read -r RAW_JSON || exit 0
[ -z "$RAW_JSON" ] && exit 0

# Step 1: Extract fields
EVENT_NAME=$(echo "$RAW_JSON" | grep -o '"event":"[^"]*' | cut -d'"' -f4)
SOURCE=$(echo "$RAW_JSON" | grep -o '"source":"[^"]*' | cut -d'"' -f4)

# Step 2: Handle event (example: custom logging or webhook delivery)
echo "[CustomOutput] Dispatched event: $EVENT_NAME from $SOURCE"

# To send a webhook, simply do:
# curl -s -X POST "https://my-webhook.com/endpoint" -H "Content-Type: application/json" -d "$RAW_JSON" >/dev/null 2>&1 || true

exit 0
