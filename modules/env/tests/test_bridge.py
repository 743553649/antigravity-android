#!/usr/bin/env python3
"""
test_bridge.py - Unit tests for System Gateway client and command formatting.
"""
import unittest
import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_ROOT = os.path.dirname(TESTS_DIR)
sys.path.insert(0, os.path.join(ENV_ROOT, "bridge"))

import client
import commands

class TestBridge(unittest.TestCase):
    def test_01_command_fallback(self):
        # Sending command to offline gateway returns fallback dictionary without raising exception
        offline_url = "http://127.0.0.1:59998/gateway"
        res = client.send_command("notify", {"title": "Title", "progress": 50}, gateway_url=offline_url)
        self.assertIn("fallback", res)
        self.assertEqual(res["packet"]["command"], "notify")
        self.assertEqual(res["packet"]["payload"]["title"], "Title")
        self.assertEqual(res["packet"]["payload"]["progress"], 50)

    def test_02_open_url_format(self):
        offline_url = "http://127.0.0.1:59998/gateway"
        res = client.send_command("open_url", {"url": "https://antigravity.google/auth"}, gateway_url=offline_url)
        self.assertEqual(res["packet"]["command"], "open_url")
        self.assertEqual(res["packet"]["payload"]["url"], "https://antigravity.google/auth")

    def test_03_wakelock_format(self):
        offline_url = "http://127.0.0.1:59998/gateway"
        res = client.send_command("wakelock", {"action": "acquire", "tag": "build_apk"}, gateway_url=offline_url)
        self.assertEqual(res["packet"]["command"], "wakelock")
        self.assertEqual(res["packet"]["payload"]["action"], "acquire")

if __name__ == "__main__":
    unittest.main()
