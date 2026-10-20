#!/usr/bin/env python3
"""
test_cli.py - Unit tests for modules/env/cli (agy_system.py and agy_logs.py).
"""
import unittest
import subprocess
import sys
import os
import json

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_DIR = os.path.dirname(TESTS_DIR)
CLI_DIR = os.path.join(ENV_DIR, "cli")


class TestCli(unittest.TestCase):

    def test_system_cli_help(self):
        script = os.path.join(CLI_DIR, "agy_system.py")
        res = subprocess.run([sys.executable, script, "--help"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("notify", res.stdout)
        self.assertIn("wakelock", res.stdout)
        self.assertIn("clipboard", res.stdout)

    def test_system_cli_info_json(self):
        script = os.path.join(CLI_DIR, "agy_system.py")
        res = subprocess.run([sys.executable, script, "--json", "info"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertIn("ok", data)

    def test_logs_cli_help(self):
        script = os.path.join(CLI_DIR, "agy_logs.py")
        res = subprocess.run([sys.executable, script, "--help"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("--crash", res.stdout)
        self.assertIn("--tail", res.stdout)

    def test_logs_cli_crash_check(self):
        script = os.path.join(CLI_DIR, "agy_logs.py")
        res = subprocess.run([sys.executable, script, "--crash"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)

    def test_system_cli_clipboard_json(self):
        script = os.path.join(CLI_DIR, "agy_system.py")
        res = subprocess.run([sys.executable, script, "--json", "clipboard", "get"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertIn("ok", data)

    def test_logs_cli_commands(self):
        script = os.path.join(CLI_DIR, "agy_logs.py")
        res = subprocess.run([sys.executable, script, "--commands"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)


if __name__ == "__main__":
    unittest.main()
