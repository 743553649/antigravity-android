#!/usr/bin/env python3
"""
test_pclntab_scanner.py - Unit test for AArch64 MOVZ encoding.
"""
import unittest
import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PATCHES_ROOT = os.path.dirname(TESTS_DIR)
sys.path.insert(0, os.path.join(PATCHES_ROOT, "engine"))

import pclntab_scanner

class TestPclntabScanner(unittest.TestCase):
    def test_01_encode_movz_x0(self):
        # 439 (0x1b7): MOVZ X0, #439 -> 0xd28036e0 (LE: e0 36 80 d2)
        enc_439 = pclntab_scanner.encode_movz_x0(439)
        self.assertEqual(enc_439, bytes.fromhex("e03680d2"))

        # 48 (0x30): MOVZ X0, #48 -> 0xd2800600 (LE: 00 06 80 d2)
        enc_48 = pclntab_scanner.encode_movz_x0(48)
        self.assertEqual(enc_48, bytes.fromhex("000680d2"))

        # 452 (0x1c4): MOVZ X0, #452 -> 0xd2803880 (LE: 80 38 80 d2)
        enc_452 = pclntab_scanner.encode_movz_x0(452)
        self.assertEqual(enc_452, bytes.fromhex("803880d2"))

        # 53 (0x35): MOVZ X0, #53 -> 0xd28006a0 (LE: a0 06 80 d2)
        enc_53 = pclntab_scanner.encode_movz_x0(53)
        self.assertEqual(enc_53, bytes.fromhex("a00680d2"))

if __name__ == "__main__":
    unittest.main()
