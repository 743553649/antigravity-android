#!/usr/bin/env python3
"""
test_builder.py - Unit tests for modules/builder components.
"""
import unittest
import tempfile
import zipfile
import shutil
import sys
import os

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
BUILDER_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, BUILDER_DIR)

import align


class TestBuilder(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="test_builder_")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_python_zipalign(self):
        raw_zip = os.path.join(self.tmp_dir, "raw.zip")
        aligned_zip = os.path.join(self.tmp_dir, "aligned.zip")

        # Create an unaligned zip with uncompressed entries of odd lengths
        with zipfile.ZipFile(raw_zip, "w") as z:
            z.writestr("test1.txt", "123", compress_type=zipfile.ZIP_STORED)
            z.writestr("test2.bin", "1234567", compress_type=zipfile.ZIP_STORED)
            z.writestr("compressed.dat", "Hello world compressed content", compress_type=zipfile.ZIP_DEFLATED)

        # Run pure Python 4-byte aligner
        ok = align.align_with_python(raw_zip, aligned_zip, alignment=4)
        self.assertTrue(ok)
        self.assertTrue(os.path.isfile(aligned_zip))

        # Inspect offsets in aligned zip
        with open(aligned_zip, "rb") as f:
            data = f.read()

        with zipfile.ZipFile(aligned_zip, "r") as z:
            for info in z.infolist():
                if info.compress_type == 0:
                    # In a local header: fixed 30 bytes + len(name) + len(extra)
                    # We verify data start offset is a multiple of 4
                    header_offset = info.header_offset
                    data_offset = header_offset + 30 + len(info.filename.encode("utf-8")) + len(info.extra)
                    self.assertEqual(data_offset % 4, 0, f"Entry {info.filename} at offset {data_offset} not 4-byte aligned!")


if __name__ == "__main__":
    unittest.main()
