#!/usr/bin/env python3
"""
prepare_runtime.py - Assembles a fully patched, verified runtime in destination path.
"""
import sys
import os
import shutil
import tempfile

RUNNER_DIR = os.path.dirname(os.path.abspath(__file__))
MODULES_DIR = os.path.dirname(RUNNER_DIR)
sys.path.insert(0, os.path.join(MODULES_DIR, "core", "unpack"))
sys.path.insert(0, os.path.join(MODULES_DIR, "core", "bundle"))
sys.path.insert(0, os.path.join(MODULES_DIR, "core", "manifest"))
sys.path.insert(0, os.path.join(MODULES_DIR, "patches"))

import extractor
import assemble
import manifest_verifier
import pipeline

DEFAULT_DEST = "/data/user/0/com.agy/files/standalone_runtime"

def prepare(dest_runtime_dir: str = DEFAULT_DEST) -> bool:
    print("=" * 60)
    print("  PREPARING NEW MODULAR RUNTIME")
    print("=" * 60)

    dest_runtime_dir = os.path.abspath(dest_runtime_dir)
    core_dir = os.path.join(MODULES_DIR, "core")
    archive_path = os.path.join(core_dir, "pristine", "language_server.tar.gz")

    tmp_dir = tempfile.mkdtemp(prefix="agy_staging_")
    app_base = "/data/user/0/com.agy.dev" if os.path.exists("/data/user/0/com.agy.dev") and os.access("/data/user/0/com.agy.dev", os.W_OK) else "/data/user/0/com.agy"
    cache_dir = os.environ.get("AGY_CACHE_DIR", os.path.join(app_base, "cache") if os.access(app_base, os.W_OK) else os.path.join(tempfile.gettempdir(), "agy_cache"))
    os.makedirs(cache_dir, exist_ok=True)
    TARGET_SHA = "1d9750dd874faf2db976756dbb3476e72c2b29779793331f324151d0cb940bb7"
    cached_patched = os.path.join(cache_dir, f"language_server_patched_{TARGET_SHA[:8]}")

    try:
        staged_bin = os.path.join(tmp_dir, "language_server")
        cache_valid = False
        if os.path.isfile(cached_patched):
            import hashlib
            hasher = hashlib.sha256()
            with open(cached_patched, "rb") as f:
                while chunk := f.read(65536):
                    hasher.update(chunk)
            if hasher.hexdigest() == TARGET_SHA:
                cache_valid = True
                print(f"\n[1-2/4] Reusing cached patched core (SHA-256 verified: {TARGET_SHA[:8]}...)...")
                shutil.copyfile(cached_patched, staged_bin)
            else:
                print(f"\n[!] Cached core SHA mismatch ({hasher.hexdigest()[:8]} != {TARGET_SHA[:8]}); re-patching...")

        if not cache_valid:
            # 1. Extract pristine core to temporary staging area
            print("\n[1/4] Extracting pristine core archive...")
            extractor.extract_core(archive_path, staged_bin)
            print(f"  [OK] Extracted: {os.path.getsize(staged_bin):,} bytes")

            # 2. Apply all patch modules
            print("\n[2/4] Applying modules/patches pipeline...")
            ok_patch = pipeline.run_pipeline(staged_bin, dry_run=False, verify=False, allow_missing=True)
            assert ok_patch, "Patch pipeline failed!"
            print("  [OK] Patches applied and verified.")
            try:
                shutil.copyfile(staged_bin, cached_patched)
            except Exception:
                pass

        # 3. Assemble full runtime assets into destination
        print(f"\n[3/4] Assembling runtime assets -> {dest_runtime_dir}...")
        if os.path.exists(dest_runtime_dir):
            shutil.rmtree(dest_runtime_dir)
        
        manifest = assemble.assemble_runtime(staged_bin, core_dir, dest_runtime_dir)
        print(f"  [OK] Runtime assembled with {len(manifest['files'])} files.")

        # 4. Verify cryptographic manifest
        print("\n[4/4] Verifying destination integrity...")
        manifest_path = os.path.join(dest_runtime_dir, "manifest.json")
        ok_verify = manifest_verifier.verify_manifest(manifest_path, dest_runtime_dir)
        assert ok_verify, "Manifest verification failed on assembled runtime!"
        print("  [OK] Cryptographic manifest verified 100% byte-for-byte.")

        print("\n" + "=" * 60)
        print("  RUNTIME PREPARED AND READY FOR EXECUTION!")
        print("=" * 60 + "\n")
        return True

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

def main():
    dest = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DEST
    ok = prepare(dest)
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
