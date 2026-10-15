#!/usr/bin/env python3
"""
manifest_verifier.py - Validates directory files against a manifest.json.
"""
import sys
import os
import json
import hashlib

def hash_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().lower()

def verify_manifest(manifest_path: str, target_dir: str) -> bool:
    if not os.path.isfile(manifest_path):
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    if not os.path.isdir(target_dir):
        raise NotADirectoryError(f"Target directory not found: {target_dir}")
    
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    expected_files = data.get("files", {})
    errors = []

    for rel_path, expected_hash in expected_files.items():
        full_path = os.path.join(target_dir, rel_path)
        if not os.path.isfile(full_path):
            errors.append(f"Missing file: {rel_path}")
            continue
        actual_hash = hash_file(full_path)
        if actual_hash != expected_hash.lower():
            errors.append(f"Corrupted file: {rel_path} (expected {expected_hash}, got {actual_hash})")

    if errors:
        for err in errors:
            print(f"[FAIL] {err}", file=sys.stderr)
        return False
    
    return True

def main():
    if len(sys.argv) < 3 or sys.argv[1] in ("-h", "--help"):
        print("Usage: manifest_verifier.py <manifest_json_path> <target_dir>")
        sys.exit(1)
    
    manifest_p = sys.argv[1]
    target_d = sys.argv[2]

    try:
        ok = verify_manifest(manifest_p, target_d)
        if ok:
            print(f"[OK] All files in {target_d} strictly match {manifest_p}")
            sys.exit(0)
        else:
            sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Verification failed: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
