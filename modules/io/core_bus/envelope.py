#!/usr/bin/env python3
"""
envelope.py - Creates, serializes, and validates standard Antigravity event envelopes.
"""
import time
import json
from typing import Dict, Any

def create_event(event_type: str, source: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
    if not event_type:
        raise ValueError("event_type cannot be empty")
    return {
        "event": event_type,
        "timestamp": int(time.time() * 1000),
        "source": source or "unknown",
        "data": data if data is not None else {}
    }

def serialize_event(envelope: Dict[str, Any]) -> str:
    return json.dumps(envelope, ensure_ascii=False)

def deserialize_event(raw_text: str) -> Dict[str, Any]:
    data = json.loads(raw_text)
    validate_event(data)
    return data

def validate_event(envelope: Dict[str, Any]) -> bool:
    required = ("event", "timestamp", "source", "data")
    for req in required:
        if req not in envelope:
            raise ValueError(f"Missing required field in envelope: '{req}'")
    if not isinstance(envelope["event"], str) or not envelope["event"].strip():
        raise ValueError("Field 'event' must be a non-empty string")
    if not isinstance(envelope["data"], dict):
        raise ValueError("Field 'data' must be a JSON dictionary")
    return True
