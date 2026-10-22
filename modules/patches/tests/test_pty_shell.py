#!/usr/bin/env python3
"""
test_pty_shell.py - Unit test for modular pty_shell patch group.
"""
import unittest
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODULES_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
sys.path.insert(0, os.path.join(MODULES_DIR, "groups", "pty_shell"))

import pty_shell

class TestPtyShell(unittest.TestCase):
    def test_signatures(self):
        self.assertEqual(len(pty_shell.TARGET), 9)
        self.assertEqual(len(pty_shell.REPLACEMENT), 9)
        self.assertEqual(pty_shell.EXPECTED_COUNT, 1)

    def test_scan_and_apply(self):
        raw = bytearray(b"header\x00/bin/bash\x00trailer")
        clean, repl = pty_shell.scan(raw)
        self.assertEqual(len(clean), 1)
        self.assertEqual(len(repl), 0)

        # Dry run
        ok, info = pty_shell.apply(raw, dry_run=True)
        self.assertTrue(ok)
        self.assertEqual(info["status"], "dry_run")
        self.assertIn(b"/bin/bash", raw)

        # Live patch
        ok, info = pty_shell.apply(raw, dry_run=False)
        self.assertTrue(ok)
        self.assertEqual(info["status"], "patched")
        self.assertNotIn(b"/bin/bash", raw)
        self.assertIn(b"/bin///sh", raw)

        # Idempotency
        ok, info = pty_shell.apply(raw, dry_run=False)
        self.assertTrue(ok)
        self.assertEqual(info["status"], "already_patched")

        # Verification
        ok, info = pty_shell.apply(raw, verify=True)
        self.assertTrue(ok)
        self.assertEqual(info["status"], "verified")

if __name__ == "__main__":
    unittest.main()
