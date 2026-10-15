"""
faccessat.py - Retargets Android-seccomp-trapped syscall.faccessat2:
MOVZ X0, #439 (0xd28036e0) -> MOVZ X0, #48 (0xd2800600).
"""
import sys
import os
from typing import Tuple, Dict, Any

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PATCHES_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
sys.path.insert(0, os.path.join(PATCHES_ROOT, "engine"))

import elf_scanner
import pclntab_scanner

FACCESSAT2_IMM = 439
FACCESSAT_IMM = 48
FUNC_NAME = "syscall.faccessat2"

def patch_in_body(body: bytes) -> Tuple[str, int, int, int]:
    old_enc = pclntab_scanner.encode_movz_x0(FACCESSAT2_IMM)
    new_enc = pclntab_scanner.encode_movz_x0(FACCESSAT_IMM)
    c_old = body.count(old_enc)
    c_new = body.count(new_enc)

    if c_old == 1 and c_new == 0:
        return "patch", body.find(old_enc), c_old, c_new
    if c_old == 0 and c_new >= 1:
        return "already", body.find(new_enc), c_old, c_new
    return "ambiguous", -1, c_old, c_new

def apply(data: bytearray, verify: bool = False, dry_run: bool = False, allow_missing: bool = False) -> Tuple[bool, Dict[str, Any]]:
    bases = elf_scanner.find_elf_headers(bytes(data))
    if not bases:
        return False, {"name": "faccessat", "error": "no_elf_found"}

    info = {"name": "faccessat", "patched_sites": [], "already_sites": []}
    ok = True

    for idx, base in enumerate(bases):
        region_end = bases[idx + 1] if idx + 1 < len(bases) else len(data)
        text = elf_scanner.get_text_section(bytes(data), base)
        if text is None:
            continue
        text_off, _ = text
        pcln = pclntab_scanner.find_pclntab(bytes(data), base, region_end)
        if pcln is None:
            continue

        found = pclntab_scanner.find_function(bytes(data), pcln, FUNC_NAME)
        if found is None:
            if base == 0 and not allow_missing:
                ok = False
            continue

        entry_off, size = found
        if size <= 0:
            ok = False
            continue

        start = text_off + entry_off
        end = start + size
        body = bytes(data[start:end])
        status, rel_off, c_old, c_new = patch_in_body(body)

        if status == "patch":
            file_off = start + rel_off
            info["patched_sites"].append(hex(file_off))
            if not verify and not dry_run:
                new_enc = pclntab_scanner.encode_movz_x0(FACCESSAT_IMM)
                data[file_off:file_off + 4] = new_enc
        elif status == "already":
            info["already_sites"].append(hex(start + rel_off))
        else:
            ok = False

    if verify:
        v_ok = ok and (len(info["already_sites"]) >= 1)
        info["status"] = "verified" if v_ok else "unverified"
        return v_ok, info

    if dry_run:
        info["status"] = "dry_run" if len(info["patched_sites"]) > 0 else "already_patched"
    else:
        info["status"] = "patched" if len(info["patched_sites"]) > 0 else "already_patched"
    return ok, info
