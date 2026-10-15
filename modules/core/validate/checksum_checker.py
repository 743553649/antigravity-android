#!/usr/bin/env python3
"""
checksum_checker.py - Validates SHA-256 checksum of a file against expected value.
"""
import sys
import hashlib
import os

def calculate_sha256(file_path: str) -> str:
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().lower()

def verify_checksum(file_path: str, expected_hash: str) -> bool:
    actual = calculate_sha256(file_path)
    if actual != expected_hash.strip().lower():
        raise ValueError(f"Checksum mismatch for {file_path}:\n  Expected: {expected_hash.lower()}\n  Actual:   {actual}")
    return True

def main():
    if len(sys.argv) < 3 or sys.argv[1] in ("-h", "--help"):
        print("Usage: checksum_checker.py <file_path> <expected_sha256>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    expected = sys.argv[2]

    try:
        if verify_checksum(file_path, expected):
            print(f"[OK] Checksum verified: {expected.lower()}")
            sys.exit(0)
    except Exception as e:
        print(f"[FAIL] {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
