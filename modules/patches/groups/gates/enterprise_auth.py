"""
enterprise_auth.py - Patches authclient.(*EnterpriseAuthValidator).Validate gate:
ldrb w3,[x0,#8] -> mov w3,#1 ; strb w3,[x0,#8] (23 00 80 52 03 20 00 39).
"""
import re
from typing import Tuple, Dict, Any, List

_ARM64_TBZ_W3_BIT0 = rb"[\x03\x23\x43\x63\x83\xa3\xc3\xe3]..\x36"
_ARM64_TOKEN_SETUP = rb"(?:....){1,2}\x03\x10\x06\xa9"
SIG_MGR_RAW = re.compile(rb"(\x03\x20\x40\x39" + _ARM64_TBZ_W3_BIT0 + _ARM64_TOKEN_SETUP + rb")", re.S)
SIG_MGR_PATCHED = re.compile(rb"(\x23\x00\x80\x52\x03\x20\x00\x39" + _ARM64_TOKEN_SETUP + rb")", re.S)
REPL_MGR = b"\x23\x00\x80\x52\x03\x20\x00\x39"
EXPECTED_COUNT = 1

def scan(data: bytes) -> Tuple[List[int], List[int]]:
    raw = [m.start(1) for m in SIG_MGR_RAW.finditer(data)]
    pat = [m.start(1) for m in SIG_MGR_PATCHED.finditer(data)]
    return raw, pat

def apply(data: bytearray, verify: bool = False, dry_run: bool = False, allow_missing: bool = False) -> Tuple[bool, Dict[str, Any]]:
    raw, pat = scan(data)
    total = len(raw) + len(pat)

    info = {
        "name": "enterprise_auth_gate",
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
            data[off:off + len(REPL_MGR)] = REPL_MGR
        info["status"] = "patched"
    else:
        info["status"] = "dry_run"

    return True, info
