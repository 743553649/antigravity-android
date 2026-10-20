"""
pclntab_scanner.py - Resolves Go runtime functions via pclntab and encodes AArch64 MOVZ instructions.
"""
import struct
from typing import Optional, Tuple, Dict, Any, Union

PCLN_MAGICS = (b"\xf1\xff\xff\xff", b"\xf2\xff\xff\xff", b"\xf0\xff\xff\xff")

def encode_movz_x0(imm: int) -> bytes:
    """Encode AArch64 MOVZ X0, #imm"""
    return struct.pack("<I", 0xD2800000 | (imm << 5) | 0)

def find_pclntab(data: Union[bytes, bytearray, memoryview], base: int, region_end: int) -> Optional[Dict[str, Any]]:
    for magic in PCLN_MAGICS:
        pos = base
        while True:
            pos = data.find(magic, pos, region_end)
            if pos < 0:
                break
            if pos + 72 <= len(data):
                try:
                    f = struct.unpack_from("<IBBBBQQQQQQQQ", data, pos)
                except struct.error:
                    f = None
                if f is not None:
                    min_lc, ptr_size, nfunc = f[3], f[4], f[5]
                    funcname_off, pcln_off = f[8], f[12]
                    ft = pos + funcname_off
                    pt = pos + pcln_off
                    if (
                        min_lc == 4
                        and ptr_size == 8
                        and 1 <= nfunc <= 1000000
                        and base <= ft < region_end
                        and base <= pt < region_end
                        and pt + nfunc * 8 <= len(data)
                    ):
                        return {
                            "pcln_base": pos,
                            "funcname_off": funcname_off,
                            "pcln_off": pcln_off,
                            "nfunc": nfunc
                        }
            pos += 4
    return None

def find_function(data: Union[bytes, bytearray, memoryview], pcln: Dict[str, Any], func_name: str) -> Optional[Tuple[int, int]]:
    cache = pcln.setdefault("_cache", {})
    if func_name in cache:
        return cache[func_name]

    ft = pcln["pcln_base"] + pcln["funcname_off"]
    pt = pcln["pcln_base"] + pcln["pcln_off"]
    nfunc = pcln["nfunc"]

    target_bytes = func_name.encode("utf-8") + b"\x00"
    name_offsets = set()
    pos = ft
    limit = pt if pt > ft else len(data)

    while True:
        pos = data.find(target_bytes, pos, limit)
        if pos == -1:
            break
        if pos == ft or data[pos - 1] == 0:
            name_offsets.add(pos - ft)
        pos += 1

    if not name_offsets:
        cache[func_name] = None
        return None

    for i in range(nfunc):
        entry_off, func_off = struct.unpack_from("<II", data, pt + i * 8)
        try:
            _entry, name_off = struct.unpack_from("<Ii", data, pt + func_off)
        except struct.error:
            continue
        if name_off in name_offsets:
            if i + 1 < nfunc:
                next_entry = struct.unpack_from("<II", data, pt + (i + 1) * 8)[0]
                size = next_entry - entry_off
            else:
                size = 0
            res = (entry_off, size)
            cache[func_name] = res
            return res

    cache[func_name] = None
    return None
