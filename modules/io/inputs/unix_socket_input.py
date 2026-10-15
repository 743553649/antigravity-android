#!/usr/bin/env python3
"""
unix_socket_input.py - UNIX Domain Socket input listener. Accepts IPC events and forwards to broker.
"""
import os
import sys
import socket

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
IO_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, os.path.join(IO_ROOT, "core_bus"))

import envelope
from event_broker import EventBroker

def run_socket_listener(socket_path: str, broker: EventBroker, max_connections: int = 0):
    if os.path.exists(socket_path):
        os.remove(socket_path)

    os.makedirs(os.path.dirname(os.path.abspath(socket_path)), exist_ok=True)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(socket_path)
    server.listen(5)

    connections_handled = 0
    try:
        while True:
            conn, _ = server.accept()
            with conn:
                buffer = ""
                while True:
                    chunk = conn.recv(1024).decode("utf-8", errors="ignore")
                    if not chunk:
                        break
                    buffer += chunk
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if line:
                            try:
                                data = envelope.deserialize_event(line)
                                broker.publish(data)
                            except Exception as e:
                                print(f"[SocketInput] Invalid event: {e}", file=sys.stderr)
            connections_handled += 1
            if 0 < max_connections <= connections_handled:
                break
    finally:
        server.close()
        if os.path.exists(socket_path):
            os.remove(socket_path)
    return connections_handled

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage: unix_socket_input.py <socket_path>")
        sys.exit(1)
    
    sock_path = sys.argv[1]
    broker = EventBroker()
    print(f"[SocketInput] Listening on UNIX socket: {sock_path}")
    run_socket_listener(sock_path, broker)

if __name__ == "__main__":
    main()
