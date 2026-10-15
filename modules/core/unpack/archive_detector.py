#!/usr/bin/env python3
"""
archive_detector.py - Detects the type of core binary archive or executable.
"""
import sys
import os

def detect_type(file_path: str) -> str:
    if not os.path.isfile(file_path):
        return "not_found"
    with open(file_path, "rb") as f:
        magic = f.read(4)
    if len(magic) >= 2 and magic[:2] == b"\x1f\x8b":
        return "tar_gz"
    if len(magic) >= 4 and magic[:4] == b"\x7fELF":
        return "elf"
    return "unknown"

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage: archive_detector.py <file_path>")
        sys.exit(1)
    file_path = sys.argv[1]
    res = detect_type(file_path)
    print(res)
    sys.exit(0 if res in ("tar_gz", "elf") else 1)

if __name__ == "__main__":
    main()
