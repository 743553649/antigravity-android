"""
cli_gate.py - Patches CLI gate checks: ldrb w1, [x0,#8] -> mov w1, #1 (21 00 80 52).
"""
import re
from typing import Tuple, Dict, Any, List

_CLI_TAIL = rb"\xe1\x03\x40\xb2\x01\x20\x00\x39"
SIG_CLI_RAW = re.compile(rb"(\x01\x20\x40\x39)(.{3}\x37)" + _CLI_TAIL, re.S)
SIG_CLI_PATCHED = re.compile(rb"(\x21\x00\x80\x52)(.{3}\x37)" + _CLI_TAIL, re.S)
REPL_CLI = b"\x21\x00\x80\x52"
EXPECTED_COUNT = 2

def scan(data: bytes) -> Tuple[List[int], List[int]]:
    raw = [m.start(1) for m in SIG_CLI_RAW.finditer(data)]
    pat = [m.start(1) for m in SIG_CLI_PATCHED.finditer(data)]
    return raw, pat

def apply(data: bytearray, verify: bool = False, dry_run: bool = False, allow_missing: bool = False) -> Tuple[bool, Dict[str, Any]]:
    raw, pat = scan(data)
    total = len(raw) + len(pat)

    info = {
        "name": "cli_gate",
        "expected": EXPECTED_COUNT,
        "raw_count": len(raw),
        "patched_count": len(pat),
        "raw_offsets": [hex(x) for x in raw],
        "patched_offsets": [hex(x) for x in pat]
    }

    if total == 0:
        if allow_missing:
            info["status"] = "skipped_missing"
            return True, info
        info["status"] = "missing_signature"
        return False, info

    if total != EXPECTED_COUNT:
        info["status"] = f"unexpected_count_{total}"
        return False, info

    if verify:
        ok = (len(raw) == 0 and len(pat) == EXPECTED_COUNT)
        info["status"] = "verified" if ok else "unverified"
        return ok, info

    if len(raw) == 0:
        info["status"] = "already_patched"
        return True, info

    if not dry_run:
        for off in raw:
            data[off:off + len(REPL_CLI)] = REPL_CLI
        info["status"] = "patched"
    else:
        info["status"] = "dry_run"

    return True, info
