#!/usr/bin/env python3
"""
file_hasher.py - Computes SHA-256 hash of a file using 1MB chunk streaming.
"""
import sys
import hashlib
import os

def hash_file(file_path: str) -> str:
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().lower()

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage: file_hasher.py <file_path>")
        sys.exit(1)
    
    try:
        digest = hash_file(sys.argv[1])
        print(digest)
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
