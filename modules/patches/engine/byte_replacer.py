"""
byte_replacer.py - Safe byte pattern matching and replacement engine.
"""
from typing import List, Tuple, Pattern, Union
import re

def find_offsets(data: Union[bytes, bytearray, memoryview], pattern: bytes) -> List[int]:
    offsets = []
    start = 0
    while True:
        pos = data.find(pattern, start)
        if pos == -1:
            break
        offsets.append(pos)
        start = pos + len(pattern)
    return offsets

def replace_exact(
    data: bytes,
    target: bytes,
    replacement: bytes,
    expected_count: int,
    allow_missing: bool = False
) -> Tuple[bool, bytes, int, int, List[int]]:
    assert len(target) == len(replacement), f"Target length {len(target)} != replacement length {len(replacement)}"
    
    raw_offsets = find_offsets(data, target)
    patched_offsets = find_offsets(data, replacement)
    
    count_raw = len(raw_offsets)
    count_patched = len(patched_offsets)

    if count_raw == 0 and count_patched == expected_count:
        # Already fully patched
        return True, data, 0, count_patched, patched_offsets

    if count_raw != expected_count:
        if allow_missing and count_raw == 0 and count_patched == 0:
            return True, data, 0, 0, []
        return False, data, count_raw, count_patched, raw_offsets

    # Perform replacement
    buf = bytearray(data)
    for off in raw_offsets:
        buf[off:off + len(replacement)] = replacement

    return True, bytes(buf), count_raw, count_patched + count_raw, raw_offsets
