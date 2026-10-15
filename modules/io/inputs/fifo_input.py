#!/usr/bin/env python3
"""
fifo_input.py - Named FIFO Pipe input listener. Reads incoming JSON events and publishes to broker.
"""
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
IO_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, os.path.join(IO_ROOT, "core_bus"))

import envelope
from event_broker import EventBroker

def run_fifo_listener(fifo_path: str, broker: EventBroker, max_events: int = 0):
    if not os.path.exists(fifo_path):
        os.mkfifo(fifo_path)

    events_read = 0
    try:
        while True:
            # Opening FIFO for reading blocks until a writer connects
            with open(fifo_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = envelope.deserialize_event(line)
                        broker.publish(data)
                        events_read += 1
                        if 0 < max_events <= events_read:
                            return events_read
                    except Exception as e:
                        print(f"[FifoInput] Bad event skipped: {e}", file=sys.stderr)
    except KeyboardInterrupt:
        pass
    return events_read

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage: fifo_input.py <fifo_path>")
        sys.exit(1)
    
    path = sys.argv[1]
    broker = EventBroker()
    print(f"[FifoInput] Listening on FIFO: {path}")
    run_fifo_listener(path, broker)

if __name__ == "__main__":
    main()
