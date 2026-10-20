"""
log.py - Lightweight structured logger with ANSI color output and optional JSONL streaming.
"""
import sys
import time
import json
import os
from typing import Dict, Any

COLORS = {
    "DEBUG": "\033[0;90m",
    "INFO": "\033[0;34m",
    "OK": "\033[0;32m",
    "WARN": "\033[0;33m",
    "ERROR": "\033[0;31m",
    "RESET": "\033[0m"
}

def log(level: str, tag: str, message: str, meta: Dict[str, Any] = None, jsonl_file: str = None) -> None:
    now = time.strftime("%H:%M:%S")
    no_color = os.environ.get("NO_COLOR") is not None or os.environ.get("TERM") == "dumb"
    color = "" if no_color else COLORS.get(level.upper(), "")
    reset = "" if no_color else COLORS["RESET"]

    out = sys.stderr if level.upper() == "ERROR" else sys.stdout
    print(f"{color}[{now}] [{level.upper()}] [{tag}]{reset} {message}", file=out)

    if jsonl_file:
        record = {
            "ts": int(time.time() * 1000),
            "level": level.upper(),
            "tag": tag,
            "msg": message,
            "meta": meta or {}
        }
        try:
            os.makedirs(os.path.dirname(os.path.abspath(jsonl_file)), exist_ok=True)
            with open(jsonl_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            pass
