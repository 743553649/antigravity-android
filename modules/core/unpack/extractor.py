#!/usr/bin/env python3
"""
extractor.py - Extracts language_server from archive into target destination.
"""
import sys
import os
import shutil
import tarfile

def extract_core(src_path: str, dest_path: str, binary_name: str = "language_server") -> bool:
    if not os.path.exists(src_path):
        raise FileNotFoundError(f"Source file not found: {src_path}")

    dest_dir = os.path.dirname(os.path.abspath(dest_path))
    os.makedirs(dest_dir, exist_ok=True)

    with open(src_path, "rb") as f:
        magic = f.read(4)

    if magic[:2] == b"\x1f\x8b":
        with tarfile.open(src_path, "r:gz") as tar:
            member = None
            for m in tar.getmembers():
                if os.path.basename(m.name) == binary_name:
                    member = m
                    break
            if not member:
                raise ValueError(f"Binary '{binary_name}' not found inside archive: {src_path}")
            
            with tar.extractfile(member) as source_f, open(dest_path, "wb") as dest_f:
                shutil.copyfileobj(source_f, dest_f)
    elif magic[:4] == b"\x7fELF":
        shutil.copyfile(src_path, dest_path)
    else:
        raise ValueError(f"Unsupported format in source file: {src_path}")

    return os.path.isfile(dest_path) and os.path.getsize(dest_path) > 0

def main():
    if len(sys.argv) < 3 or sys.argv[1] in ("-h", "--help"):
        print("Usage: extractor.py <source_path> <dest_binary_path> [binary_name]")
        sys.exit(1)
    
    src = sys.argv[1]
    dest = sys.argv[2]
    name = sys.argv[3] if len(sys.argv) > 3 else "language_server"

    try:
        ok = extract_core(src, dest, name)
        if ok:
            print(f"[OK] Extracted {name} -> {dest} ({os.path.getsize(dest)} bytes)")
            sys.exit(0)
    except Exception as e:
        print(f"[ERROR] Extraction failed: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
