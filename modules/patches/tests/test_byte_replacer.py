#!/usr/bin/env python3
"""
test_byte_replacer.py - Unit test for byte pattern matching and replacement.
"""
import unittest
import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PATCHES_ROOT = os.path.dirname(TESTS_DIR)
sys.path.insert(0, os.path.join(PATCHES_ROOT, "engine"))

import byte_replacer

class TestByteReplacer(unittest.TestCase):
    def test_01_find_and_replace(self):
        data = b"Hello TARGET World TARGET 123"
        target = b"TARGET"
        replacement = b"REPLAC"

        ok, new_data, count_raw, count_patched, offsets = byte_replacer.replace_exact(
            data, target, replacement, expected_count=2
        )
        self.assertTrue(ok)
        self.assertEqual(count_raw, 2)
        self.assertEqual(count_patched, 2)
        self.assertEqual(new_data, b"Hello REPLAC World REPLAC 123")

    def test_02_already_patched(self):
        data = b"Hello REPLAC World REPLAC 123"
        target = b"TARGET"
        replacement = b"REPLAC"

        ok, new_data, count_raw, count_patched, offsets = byte_replacer.replace_exact(
            data, target, replacement, expected_count=2
        )
        self.assertTrue(ok)
        self.assertEqual(count_raw, 0)
        self.assertEqual(count_patched, 2)
        self.assertEqual(new_data, data)

if __name__ == "__main__":
    unittest.main()
