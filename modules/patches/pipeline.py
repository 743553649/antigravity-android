#!/usr/bin/env python3
"""
pipeline.py - Orchestrator and CLI runner for Antigravity core binary patches.
"""
import sys
import os
import argparse
import hashlib
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(SCRIPT_DIR, "engine"))
sys.path.insert(0, os.path.join(SCRIPT_DIR, "groups", "gates"))
sys.path.insert(0, os.path.join(SCRIPT_DIR, "groups", "syscalls"))
sys.path.insert(0, os.path.join(SCRIPT_DIR, "groups", "sigill"))
sys.path.insert(0, os.path.join(SCRIPT_DIR, "groups", "resolv"))
sys.path.insert(0, os.path.join(SCRIPT_DIR, "groups", "failfast"))

import cli_gate
import enterprise_auth
import faccessat
import fchmodat
import sigill_handler
import resolv_redirect
import crash_suppressor
import reporter

ACTIVE_MODULES = [
    cli_gate,
    enterprise_auth,
    faccessat,
    fchmodat,
    sigill_handler,
    resolv_redirect,
    crash_suppressor
]

def sha256_bytes(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest().lower()

def run_pipeline(target_path: str, verify: bool = False, dry_run: bool = False, allow_missing: bool = False, manifest_path: str = None, skip_gates: bool = False) -> bool:
    skip_gates = skip_gates or (os.environ.get("NO_BYPASS") == "1") or (os.environ.get("SKIP_GATES") == "1")

    if not os.path.isfile(target_path):
        print(f"[FATAL] Target binary not found: {target_path}", file=sys.stderr)
        return False

    with open(target_path, "rb") as f:
        orig_bytes = f.read()

    sha_init = sha256_bytes(orig_bytes)
    data = bytearray(orig_bytes)
    mode = {"verify": verify, "dry_run": dry_run, "allow_missing": allow_missing, "skip_gates": skip_gates}

    print(f"[*] Core target: {target_path} ({len(data):,} bytes)")
    print(f"[*] Initial SHA-256: {sha_init}")
    if skip_gates:
        print("[*] Gate bypass disabled (--no-bypass/--skip-gates): skipping cli_gate & enterprise_auth")

    group_results = []
    overall_ok = True

    for mod in ACTIVE_MODULES:
        mod_name = mod.__name__
        if skip_gates and mod_name in ("cli_gate", "enterprise_auth"):
            print(f"  [SKIP] {mod_name:<20}: bypass disabled")
            group_results.append({"name": mod_name, "status": "skipped_no_bypass"})
            continue
        ok, info = mod.apply(data, verify=verify, dry_run=dry_run, allow_missing=allow_missing)
        group_results.append(info)
        status = info.get("status", "unknown")
        print(f"  [{'OK' if ok else 'FAIL'}] {mod_name:<20}: {status}")
        if not ok:
            overall_ok = False
            break

    if not overall_ok:
        print("[FATAL] One or more patch modules failed! Aborting without write.", file=sys.stderr)
        return False

    if verify:
        print("\n[OK] Verification PASSED: Core binary contains all required patch signatures.")
        return True

    final_bytes = bytes(data)
    sha_final = sha256_bytes(final_bytes)
    print(f"[*] Final SHA-256:   {sha_final}")

    if not dry_run:
        if sha_init != sha_final:
            with open(target_path, "wb") as f:
                f.write(final_bytes)
            print(f"[OK] Patches committed to: {target_path}")
        else:
            print("[OK] Binary was already patched. No bytes changed.")

    rep = reporter.build_report(target_path, sha_init, sha_final, len(final_bytes), group_results, mode, overall_ok)
    if manifest_path:
        os.makedirs(os.path.dirname(os.path.abspath(manifest_path)), exist_ok=True)
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(rep, f, indent=2)
            f.write("\n")
        print(f"[*] Report saved to: {manifest_path}")

    return True

def main():
    parser = argparse.ArgumentParser(description="Antigravity modular core binary patcher.")
    parser.add_argument("target", help="Path to staged core binary")
    parser.add_argument("--verify", action="store_true", help="Verify presence of patches without modifying")
    parser.add_argument("--dry-run", action="store_true", help="Compute patches without writing")
    parser.add_argument("--allow-missing", action="store_true", help="Tolerate missing signatures")
    parser.add_argument("--manifest", help="Optional path to output manifest JSON report")
    parser.add_argument("--skip-gates", "--no-bypass", "--no-gates", action="store_true", dest="skip_gates", help="Disable region and auth gates bypass")

    args = parser.parse_args()
    ok = run_pipeline(args.target, verify=args.verify, dry_run=args.dry_run, allow_missing=args.allow_missing, manifest_path=args.manifest, skip_gates=args.skip_gates)
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
