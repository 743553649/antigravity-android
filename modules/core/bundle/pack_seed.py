#!/usr/bin/env python3
"""
pack_seed.py - Copies default state, seed protobuf configurations, and agent guidelines into seed/.
"""
import sys
import os
import shutil

def pack_seed(seed_dir: str, dest_seed_dir: str) -> list:
    if not os.path.isdir(seed_dir):
        raise NotADirectoryError(f"Seed directory not found: {seed_dir}")
    os.makedirs(dest_seed_dir, exist_ok=True)
    
    copied = []
    for item in sorted(os.listdir(seed_dir)):
        src = os.path.join(seed_dir, item)
        if os.path.isfile(src):
            dst = os.path.join(dest_seed_dir, item)
            shutil.copyfile(src, dst)
            copied.append(item)
            
    return copied

def main():
    if len(sys.argv) < 3 or sys.argv[1] in ("-h", "--help"):
        print("Usage: pack_seed.py <seed_dir> <dest_seed_dir>")
        sys.exit(1)
    
    try:
        seeds = pack_seed(sys.argv[1], sys.argv[2])
        print(f"[OK] Packed {len(seeds)} seed files to {sys.argv[2]}")
        sys.exit(0)
    except Exception as e:
        print(f"[ERROR] Failed packing seeds: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
