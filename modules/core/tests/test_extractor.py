#!/usr/bin/env python3
"""
test_extractor.py - Unit tests for core archive detection and extraction.
"""
import unittest
import os
import sys
import tempfile
import shutil

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE_ROOT = os.path.dirname(TESTS_DIR)
sys.path.insert(0, os.path.join(MODULE_ROOT, "unpack"))

import archive_detector
import extractor
import permissions

class TestCoreExtractor(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.archive_path = os.path.join(MODULE_ROOT, "pristine", "language_server.tar.gz")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_01_detect_archive_type(self):
        self.assertTrue(os.path.isfile(self.archive_path), f"Archive missing: {self.archive_path}")
        t = archive_detector.detect_type(self.archive_path)
        self.assertEqual(t, "tar_gz")

    def test_02_extract_binary(self):
        dest_bin = os.path.join(self.tmp_dir, "language_server")
        ok = extractor.extract_core(self.archive_path, dest_bin)
        self.assertTrue(ok)
        self.assertTrue(os.path.isfile(dest_bin))
        self.assertGreater(os.path.getsize(dest_bin), 100 * 1024 * 1024)

        # Detect extracted binary format
        t = archive_detector.detect_type(dest_bin)
        self.assertEqual(t, "elf")

    def test_03_permissions(self):
        sample_file = os.path.join(self.tmp_dir, "sample.sh")
        with open(sample_file, "w") as f:
            f.write("#!/bin/sh\necho test\n")
        permissions.make_executable(sample_file)
        mode = os.stat(sample_file).st_mode
        self.assertTrue(bool(mode & 0o111))

if __name__ == "__main__":
    unittest.main()
