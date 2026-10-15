#!/usr/bin/env python3
"""
unix_socket_emitter.py - Forwards incoming JSON event to a subscriber UNIX domain socket.
"""
import sys
import os
import socket

def emit_to_socket(raw_line: str, sock_path: str) -> bool:
    if not os.path.exists(sock_path):
        return False
    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(sock_path)
        client.sendall((raw_line.strip() + "\n").encode("utf-8"))
        client.close()
        return True
    except Exception:
        return False

def main():
    if len(sys.argv) < 2:
        sys.exit(0)
    sock_path = sys.argv[1]
    for line in sys.stdin:
        if line.strip():
            emit_to_socket(line, sock_path)

if __name__ == "__main__":
    main()
