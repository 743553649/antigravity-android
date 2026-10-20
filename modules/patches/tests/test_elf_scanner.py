#!/usr/bin/env python3
"""
test_elf_scanner.py - Unit tests for ELF scanner, stripped binary fallback, and boundary checks.
"""
import unittest
import os
import sys
import struct

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PATCHES_ROOT = os.path.dirname(TESTS_DIR)
sys.path.insert(0, os.path.join(PATCHES_ROOT, "engine"))

import elf_scanner

class TestElfScanner(unittest.TestCase):
    def _create_minimal_elf(self, stripped: bool = False, bad_shstr: bool = False) -> bytearray:
        buf = bytearray(1024)
        # e_ident
        buf[0:4] = elf_scanner.ELF_MAGIC
        buf[4] = 2  # ELFCLASS64
        buf[5] = 1  # ELFDATA2LSB
        buf[6] = 1  # EV_CURRENT
        # e_type = 2 (ET_EXEC), e_machine = 183 (EM_AARCH64)
        struct.pack_into("<H", buf, 16, 2)
        struct.pack_into("<H", buf, 18, 183)

        # Program headers: e_phoff = 64, e_phentsize = 56, e_phnum = 1
        struct.pack_into("<Q", buf, 32, 64)
        struct.pack_into("<H", buf, 54, 56)
        struct.pack_into("<H", buf, 56, 1)

        # Phdr at 64: PT_LOAD = 1, flags = 5 (PF_R | PF_X), p_offset = 256, p_filesz = 128
        struct.pack_into("<II", buf, 64, 1, 5)
        struct.pack_into("<Q", buf, 64 + 8, 256)
        struct.pack_into("<Q", buf, 64 + 32, 128)

        if stripped:
            # e_shoff = 0, e_shentsize = 0, e_shnum = 0, e_shstrndx = 0
            struct.pack_into("<Q", buf, 40, 0)
            struct.pack_into("<H", buf, 58, 0)
            struct.pack_into("<H", buf, 60, 0)
            struct.pack_into("<H", buf, 62, 0)
        else:
            # Section headers at 512: 2 sections (NULL and .text and .shstrtab)
            # shstr at 400: b"\x00.text\x00.shstrtab\x00"
            shstr = b"\x00.text\x00.shstrtab\x00"
            buf[400:400 + len(shstr)] = shstr

            struct.pack_into("<Q", buf, 40, 512)
            struct.pack_into("<H", buf, 58, 64)
            struct.pack_into("<H", buf, 60, 3)
            struct.pack_into("<H", buf, 62, 2)  # .shstrtab is section index 2

            # Section 0: NULL
            # Section 1: .text (name_off = 1), offset = 256, size = 128
            struct.pack_into("<I", buf, 512 + 64, 1)
            struct.pack_into("<QQ", buf, 512 + 64 + 24, 256, 128)

            # Section 2: .shstrtab (name_off = 7), offset = 400, size = len(shstr)
            shstr_off = 9999 if bad_shstr else 400
            struct.pack_into("<I", buf, 512 + 128, 7)
            struct.pack_into("<QQ", buf, 512 + 128 + 24, shstr_off, len(shstr))

        return buf

    def test_01_valid_elf64(self):
        buf = self._create_minimal_elf(stripped=False)
        self.assertTrue(elf_scanner.is_valid_elf64(buf, 0))
        text = elf_scanner.get_text_section(buf, 0)
        self.assertEqual(text, (256, 128))

    def test_02_stripped_binary_program_headers(self):
        buf = self._create_minimal_elf(stripped=True)
        # Must be recognized as valid ELF64 even with e_shnum == 0
        self.assertTrue(elf_scanner.is_valid_elf64(buf, 0))
        # get_text_section must fall back to PT_LOAD executable segment
        text = elf_scanner.get_text_section(buf, 0)
        self.assertEqual(text, (256, 128))

    def test_03_boundary_checks(self):
        # Out-of-bounds shstr offset should not crash, must return None or safe fallback
        buf = self._create_minimal_elf(bad_shstr=True)
        self.assertTrue(elf_scanner.is_valid_elf64(buf, 0))
        text = elf_scanner.get_text_section(buf, 0)
        # Falls back to PT_LOAD segment safely
        self.assertEqual(text, (256, 128))

        # Truncated buffer
        short_buf = buf[:32]
        self.assertFalse(elf_scanner.is_valid_elf64(short_buf, 0))
        self.assertIsNone(elf_scanner.get_text_section(short_buf, 0))

    def test_04_find_elf_headers(self):
        buf = self._create_minimal_elf(stripped=False)
        bases = elf_scanner.find_elf_headers(buf)
        self.assertEqual(bases, [0])

if __name__ == "__main__":
    unittest.main()
