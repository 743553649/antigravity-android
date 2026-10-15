#!/usr/bin/env python3
"""
file_sink.py - Appends incoming events to an append-only JSONL log file.
Reads from stdin.
"""
import sys
import os

DEFAULT_LOG = os.path.expanduser("~/.gemini/events.jsonl")

def append_event(line: str, log_path: str = None) -> None:
    target = log_path or os.environ.get("AGY_EVENT_LOG", DEFAULT_LOG)
    os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
    with open(target, "a", encoding="utf-8") as f:
        f.write(line.strip() + "\n")

def main():
    target = sys.argv[1] if len(sys.argv) > 1 else None
    for line in sys.stdin:
        line = line.strip()
        if line:
            append_event(line, target)

if __name__ == "__main__":
    main()
