"""
pty_shell.py - Modular length-preserving PTY shell patch: /bin/bash -> /bin///sh (9 bytes).

Ensures the core language_server PTY spawner routes to /system/bin/sh (or POSIX /bin///sh)
instead of failing on Android where /bin/bash is nonexistent.
"""
from typing import Tuple, Dict, Any, List, Union

TARGET = b"/bin/bash"
REPLACEMENT = b"/bin///sh"
EXPECTED_COUNT = 1

def scan(data: Union[bytes, bytearray, memoryview]) -> Tuple[List[int], List[int]]:
    """Scan data for clean target occurrences and already-patched replacement occurrences."""
    clean = []
    pos = 0
    while True:
        pos = data.find(TARGET, pos)
        if pos < 0:
            break
        clean.append(pos)
        pos += len(TARGET)

    repl = []
    pos = 0
    while True:
        pos = data.find(REPLACEMENT, pos)
        if pos < 0:
            break
        repl.append(pos)
        pos += len(REPLACEMENT)

    return clean, repl

def apply(data: bytearray, verify: bool = False, dry_run: bool = False, allow_missing: bool = False) -> Tuple[bool, Dict[str, Any]]:
    clean, repl = scan(data)
    total = len(clean) + len(repl)

    info = {
        "name": "pty_shell",
        "expected": EXPECTED_COUNT,
        "clean_count": len(clean),
        "replacement_count": len(repl),
        "clean_offsets": [hex(x) for x in clean],
        "replacement_offsets": [hex(x) for x in repl]
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
        ok = (len(clean) == 0 and len(repl) == EXPECTED_COUNT)
        info["status"] = "verified" if ok else "unverified"
        return ok, info

    if len(clean) == 0:
        info["status"] = "already_patched"
        return True, info

    if not dry_run:
        for pos in clean:
            data[pos:pos + len(REPLACEMENT)] = REPLACEMENT
        info["status"] = "patched"
    else:
        info["status"] = "dry_run"

    return True, info
