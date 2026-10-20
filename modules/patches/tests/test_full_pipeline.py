#!/usr/bin/env python3
"""
test_full_pipeline.py - Full integration test for the modular patch pipeline on language_server.
"""
import unittest
import os
import sys
import tempfile
import shutil

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PATCHES_ROOT = os.path.dirname(TESTS_DIR)
MODULES_ROOT = os.path.dirname(PATCHES_ROOT)
sys.path.insert(0, PATCHES_ROOT)
sys.path.insert(0, os.path.join(MODULES_ROOT, "core", "unpack"))

import pipeline
import extractor

EXPECTED_FINAL_SHA = "1d9750dd874faf2db976756dbb3476e72c2b29779793331f324151d0cb940bb7"

class TestFullPipeline(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.archive_path = os.path.join(MODULES_ROOT, "core", "pristine", "language_server.tar.gz")
        self.staged_bin = os.path.join(self.tmp_dir, "language_server")
        extractor.extract_core(self.archive_path, self.staged_bin)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_01_dry_run_pipeline(self):
        ok = pipeline.run_pipeline(self.staged_bin, dry_run=True, allow_missing=True)
        self.assertTrue(ok)

    def test_02_apply_and_verify(self):
        # 1. Apply patches
        manifest_out = os.path.join(self.tmp_dir, "runtime.manifest.json")
        ok_apply = pipeline.run_pipeline(self.staged_bin, allow_missing=False, manifest_path=manifest_out)
        self.assertTrue(ok_apply)
        self.assertTrue(os.path.isfile(manifest_out))

        # Check final SHA-256 matches exact reference from spec
        with open(self.staged_bin, "rb") as f:
            final_sha = pipeline.sha256_bytes(f.read())
        self.assertEqual(final_sha, EXPECTED_FINAL_SHA)

        # 2. Verify pipeline
        ok_verify = pipeline.run_pipeline(self.staged_bin, verify=True, allow_missing=False)
        self.assertTrue(ok_verify)

        # 3. Idempotent re-apply
        ok_reapply = pipeline.run_pipeline(self.staged_bin, allow_missing=False)
        self.assertTrue(ok_reapply)

    def test_03_full_pipeline_without_allow_missing(self):
        # With all modules including crash_suppressor present, allow_missing=False succeeds
        ok = pipeline.run_pipeline(self.staged_bin, dry_run=True, allow_missing=False)
        self.assertTrue(ok)

if __name__ == "__main__":
    unittest.main()
