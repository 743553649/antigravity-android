#!/usr/bin/env python3
"""
test_manifest.py - Unit tests for manifest generation and integrity verification.
"""
import unittest
import os
import sys
import tempfile
import shutil

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE_ROOT = os.path.dirname(TESTS_DIR)
sys.path.insert(0, os.path.join(MODULE_ROOT, "manifest"))

import file_hasher
import manifest_builder
import manifest_verifier

class TestManifest(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.file1 = os.path.join(self.tmp_dir, "test1.txt")
        self.file2 = os.path.join(self.tmp_dir, "sub", "test2.bin")
        os.makedirs(os.path.dirname(self.file2), exist_ok=True)
        
        with open(self.file1, "wb") as f:
            f.write(b"Antigravity Core Test 1")
        with open(self.file2, "wb") as f:
            f.write(b"\x00\x01\x02\x03Core Binary Content")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_01_file_hasher(self):
        h = file_hasher.hash_file(self.file1)
        self.assertEqual(len(h), 64)

    def test_02_build_and_verify_manifest(self):
        manifest_path = os.path.join(self.tmp_dir, "manifest.json")
        m = manifest_builder.build_manifest(self.tmp_dir, manifest_path)
        self.assertIn("files", m)
        self.assertEqual(len(m["files"]), 2)
        
        # Verify valid manifest
        self.assertTrue(manifest_verifier.verify_manifest(manifest_path, self.tmp_dir))

    def test_03_detect_tampering(self):
        manifest_path = os.path.join(self.tmp_dir, "manifest.json")
        manifest_builder.build_manifest(self.tmp_dir, manifest_path)

        # Tamper file1
        with open(self.file1, "wb") as f:
            f.write(b"Tampered payload")
        
        self.assertFalse(manifest_verifier.verify_manifest(manifest_path, self.tmp_dir))

if __name__ == "__main__":
    unittest.main()
