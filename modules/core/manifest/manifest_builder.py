#!/usr/bin/env python3
"""
manifest_builder.py - Scans runtime directory and generates manifest.json.
"""
import sys
import os
import json
import time
import hashlib

def hash_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().lower()

def build_manifest(runtime_dir: str, out_file: str = None) -> dict:
    runtime_dir = os.path.abspath(runtime_dir)
    if not os.path.isdir(runtime_dir):
        raise NotADirectoryError(f"Directory not found: {runtime_dir}")
    
    files = {}
    for root, _, filenames in os.walk(runtime_dir):
        for fn in sorted(filenames):
            full_path = os.path.join(root, fn)
            rel_path = os.path.relpath(full_path, runtime_dir).replace(os.sep, "/")
            if rel_path == "manifest.json":
                continue
            files[rel_path] = hash_file(full_path)
    
    manifest_data = {
        "schema": 1,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "files": files
    }

    if out_file:
        out_path = os.path.abspath(out_file)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2, sort_keys=True)
            f.write("\n")
            
    return manifest_data

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage: manifest_builder.py <runtime_dir> [output_manifest_path]")
        sys.exit(1)
    
    rt_dir = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(rt_dir, "manifest.json")
    
    try:
        manifest = build_manifest(rt_dir, out_path)
        print(f"[OK] Manifest generated: {len(manifest['files'])} files hashed -> {out_path}")
        sys.exit(0)
    except Exception as e:
        print(f"[ERROR] Manifest generation failed: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
