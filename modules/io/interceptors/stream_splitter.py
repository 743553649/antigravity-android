#!/usr/bin/env python3
"""
stream_splitter.py - Duplicates a process stream (stdout/stderr) while running interceptor filters to publish events to the bus.
"""
import sys
import os
from typing import List, Callable

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
IO_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, os.path.join(IO_ROOT, "core_bus"))
sys.path.insert(0, os.path.join(SCRIPT_DIR, "filters"))

import envelope
from event_broker import EventBroker
import filter_open_url
import filter_task_events
import filter_error_alerts

FILTERS: List[Callable] = [
    filter_open_url.filter_line,
    filter_task_events.filter_line,
    filter_error_alerts.filter_line
]

def process_stream(stream_in, stream_out, broker: EventBroker, max_lines: int = 0):
    lines_processed = 0
    events_emitted = 0

    for line in stream_in:
        # Echo to stdout/stderr
        if stream_out:
            stream_out.write(line)
            stream_out.flush()

        # Run through filters
        for f in FILTERS:
            try:
                res = f(line)
                if res:
                    env = envelope.create_event(res["event"], res.get("source", "stream"), res.get("data", {}))
                    broker.publish(env)
                    events_emitted += 1
            except Exception as e:
                print(f"[StreamSplitter] Filter error: {e}", file=sys.stderr)

        lines_processed += 1
        if 0 < max_lines <= lines_processed:
            break

    return lines_processed, events_emitted

def main():
    broker = EventBroker()
    process_stream(sys.stdin, sys.stdout, broker)

if __name__ == "__main__":
    main()
