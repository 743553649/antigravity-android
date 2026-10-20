"""
elf_scanner.py - Locates ELF headers and .text sections in 64-bit Little-Endian binaries.
"""
import struct
from typing import List, Tuple, Optional, Union

ELF_MAGIC = b"\x7fELF"
EM_AARCH64 = 183

def is_valid_elf64(data: Union[bytes, bytearray, memoryview], base: int) -> bool:
    if base + 64 > len(data):
        return False
    if data[base:base + 4] != ELF_MAGIC or data[base + 4] != 2 or data[base + 5] != 1:
        return False
    e_type = struct.unpack_from("<H", data, base + 16)[0]
    e_machine = struct.unpack_from("<H", data, base + 18)[0]
    if e_machine != EM_AARCH64 or e_type not in (2, 3):
        return False

    e_phoff = struct.unpack_from("<Q", data, base + 32)[0]
    e_phentsize = struct.unpack_from("<H", data, base + 54)[0]
    e_phnum = struct.unpack_from("<H", data, base + 56)[0]
    if e_phoff > 0 and e_phnum > 0:
        if e_phentsize != 56 or (base + e_phoff + e_phnum * e_phentsize) > len(data):
            return False

    e_shoff = struct.unpack_from("<Q", data, base + 40)[0]
    e_shentsize = struct.unpack_from("<H", data, base + 58)[0]
    e_shnum = struct.unpack_from("<H", data, base + 60)[0]
    e_shstrndx = struct.unpack_from("<H", data, base + 62)[0]
    if e_shnum > 0 and e_shoff > 0:
        if e_shentsize != 64 or e_shnum > 4096 or e_shstrndx >= e_shnum:
            return False
        if (base + e_shoff + e_shnum * e_shentsize) > len(data):
            return False
    return True

def find_elf_headers(data: Union[bytes, bytearray, memoryview]) -> List[int]:
    bases = []
    if is_valid_elf64(data, 0):
        bases.append(0)
    pos = 4
    while True:
        pos = data.find(ELF_MAGIC, pos)
        if pos == -1:
            break
        if is_valid_elf64(data, pos):
            bases.append(pos)
        pos += 4
    return bases

def get_text_section(data: Union[bytes, bytearray, memoryview], base: int) -> Optional[Tuple[int, int]]:
    if base + 64 > len(data):
        return None
    e_shoff = struct.unpack_from("<Q", data, base + 40)[0]
    e_shentsize = struct.unpack_from("<H", data, base + 58)[0]
    e_shnum = struct.unpack_from("<H", data, base + 60)[0]
    e_shstrndx = struct.unpack_from("<H", data, base + 62)[0]

    if e_shoff > 0 and e_shnum > 0 and e_shentsize == 64 and e_shstrndx < e_shnum:
        table_end = base + e_shoff + e_shnum * e_shentsize
        if table_end <= len(data):
            shstr_entry = base + e_shoff + e_shstrndx * e_shentsize
            if shstr_entry + 32 <= len(data):
                shstr_off, shstr_size = struct.unpack_from("<QQ", data, shstr_entry + 24)
                shstr_start = base + shstr_off
                shstr_end = shstr_start + shstr_size
                if 0 <= shstr_start < len(data) and shstr_end <= len(data):
                    shstr = data[shstr_start:shstr_end]
                    for i in range(e_shnum):
                        s_entry = base + e_shoff + i * e_shentsize
                        if s_entry + 32 <= len(data):
                            sh_name = struct.unpack_from("<I", data, s_entry)[0]
                            sh_offset, sh_size = struct.unpack_from("<QQ", data, s_entry + 24)
                            if 0 <= sh_name < len(shstr):
                                end = shstr.find(b"\x00", sh_name)
                                sec_name = shstr[sh_name:end] if end != -1 else shstr[sh_name:]
                                if sec_name == b".text":
                                    text_start = base + sh_offset
                                    if 0 <= text_start < len(data) and text_start + sh_size <= len(data):
                                        return text_start, sh_size

    # Fallback for stripped binaries via Program Headers (PT_LOAD executable)
    e_phoff = struct.unpack_from("<Q", data, base + 32)[0]
    e_phentsize = struct.unpack_from("<H", data, base + 54)[0]
    e_phnum = struct.unpack_from("<H", data, base + 56)[0]
    if e_phoff > 0 and e_phnum > 0 and e_phentsize >= 56:
        for idx in range(e_phnum):
            ph_entry = base + e_phoff + idx * e_phentsize
            if ph_entry + 56 <= len(data):
                p_type, p_flags = struct.unpack_from("<II", data, ph_entry)
                p_offset = struct.unpack_from("<Q", data, ph_entry + 8)[0]
                p_filesz = struct.unpack_from("<Q", data, ph_entry + 32)[0]
                # PT_LOAD = 1, PF_X = 1
                if p_type == 1 and (p_flags & 1):
                    seg_start = base + p_offset
                    if 0 <= seg_start < len(data) and p_filesz > 0:
                        seg_size = min(p_filesz, len(data) - seg_start)
                        return seg_start, seg_size

    return None
