#!/usr/bin/env python3
"""
stream_splitter.py - Duplicates a process stream (stdout/stderr) while running interceptor filters to publish events to the bus.
"""
import sys
import os
import queue
import threading
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

def _worker_loop(event_queue: queue.Queue, broker: EventBroker):
    while True:
        try:
            item = event_queue.get()
            if item is None:
                event_queue.task_done()
                break
            try:
                broker.publish(item)
            except Exception as e:
                print(f"[StreamSplitter] Worker error publishing event: {e}", file=sys.stderr)
            finally:
                event_queue.task_done()
        except Exception as e:
            print(f"[StreamSplitter] Worker loop error: {e}", file=sys.stderr)

def process_stream(stream_in, stream_out, broker: EventBroker, max_lines: int = 0):
    lines_processed = 0
    events_emitted = 0

    event_queue: queue.Queue = queue.Queue()
    worker_thread = threading.Thread(
        target=_worker_loop,
        args=(event_queue, broker),
        daemon=True,
        name="StreamSplitterWorker"
    )
    worker_thread.start()

    try:
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
                        event_queue.put(env)
                        events_emitted += 1
                except Exception as e:
                    print(f"[StreamSplitter] Filter error: {e}", file=sys.stderr)

            lines_processed += 1
            if 0 < max_lines <= lines_processed:
                break
    finally:
        event_queue.put(None)
        worker_thread.join()

    return lines_processed, events_emitted

def main():
    broker = EventBroker()
    process_stream(sys.stdin, sys.stdout, broker)

if __name__ == "__main__":
    main()
