#!/usr/bin/env python3
"""
test_diagnostics.py - Unit tests for preflight checks and port validation.
"""
import unittest
import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_ROOT = os.path.dirname(TESTS_DIR)
sys.path.insert(0, os.path.join(ENV_ROOT, "diagnostics"))

import preflight
import port_checker

class TestDiagnostics(unittest.TestCase):
    def test_01_preflight_current_root(self):
        # Run preflight on current directory
        cwd = os.getcwd()
        res = preflight.run_preflight(app_root=cwd, min_mb_free=1)
        self.assertIn("arch", res)
        self.assertIn("free_disk_mb", res)
        self.assertTrue(res["space_ok"])
        self.assertTrue(res["write_ok"])

    def test_02_port_checker(self):
        # Port 0 or ephemeral port should be bindable
        res = port_checker.check_port_available(59123)
        self.assertIn("available", res)
        self.assertEqual(res["port"], 59123)

    def test_03_preflight_default_root(self):
        # Preflight without explicit app_root should resolve dynamically
        res = preflight.run_preflight(min_mb_free=1)
        self.assertIn("arch", res)
        self.assertIn("app_root", res)
        self.assertTrue(res["app_root"].startswith("/"))

if __name__ == "__main__":
    unittest.main()
