#!/usr/bin/env python3
"""
assemble.py - High-level orchestrator assembling the complete runtime directory.
"""
import sys
import os
import shutil
import argparse

# Local imports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, os.path.join(MODULE_ROOT, "manifest"))

import layout
import pack_binaries
import pack_libraries
import pack_certs
import pack_seed
import manifest_builder

def assemble_runtime(core_bin_path: str, module_root: str, out_dir: str, dry_run: bool = False) -> dict:
    glibc_dir = os.path.join(module_root, "glibc")
    loader_path = os.path.join(glibc_dir, "ld-linux-aarch64.so.1")
    shims_dir = os.path.join(module_root, "shims")
    certs_dir = os.path.join(module_root, "certs")
    seed_dir = os.path.join(module_root, "seed")

    print(f"[*] Assembling runtime assets -> {out_dir}")
    if dry_run:
        print("[*] (Dry-run mode: verifying inputs only)")
        assert os.path.isfile(core_bin_path), f"Missing core binary: {core_bin_path}"
        assert os.path.isfile(loader_path), f"Missing loader: {loader_path}"
        assert os.path.isdir(shims_dir), f"Missing shims: {shims_dir}"
        assert os.path.isdir(certs_dir), f"Missing certs: {certs_dir}"
        assert os.path.isdir(seed_dir), f"Missing seed: {seed_dir}"
        print("[OK] Dry-run passed. All inputs verified.")
        return {"dry_run": True}

    # 1. Create directory layout
    dirs = layout.create_layout(out_dir)

    # 2. Pack binaries and shims
    bins = pack_binaries.pack_binaries(core_bin_path, loader_path, shims_dir, dirs["bin"])
    print(f"  + Packed {len(bins)} binaries and shims")

    # 3. Pack libraries and network configs
    libs = pack_libraries.pack_libraries(glibc_dir, dirs["lib"])
    print(f"  + Packed {len(libs)} libraries and configs")

    # 4. Pack certificates
    certs = pack_certs.pack_certs(certs_dir, dirs["certs"])
    print(f"  + Packed {len(certs)} cert files")

    # 5. Pack seed
    seeds = pack_seed.pack_seed(seed_dir, dirs["seed"])
    print(f"  + Packed {len(seeds)} seed files")

    # 6. Generate manifest.json
    manifest_path = os.path.join(out_dir, "manifest.json")
    manifest = manifest_builder.build_manifest(out_dir, manifest_path)
    print(f"[OK] Assembled successfully. Manifest files: {len(manifest['files'])}")

    return manifest

def main():
    parser = argparse.ArgumentParser(description="Assemble runtime assets for Antigravity core.")
    parser.add_argument("--core-bin", required=True, help="Path to staged language_server binary")
    parser.add_argument("--module-root", default=MODULE_ROOT, help="Root path of modules/core")
    parser.add_argument("--out-dir", required=True, help="Destination directory (e.g. build/assets/runtime)")
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs without writing output")

    args = parser.parse_args()
    try:
        assemble_runtime(args.core_bin, args.module_root, args.out_dir, args.dry_run)
        sys.exit(0)
    except Exception as e:
        print(f"[FATAL] Assembly failed: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
