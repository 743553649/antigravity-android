#!/usr/bin/env python3
"""
modules/io/tests/test_model_adapter_http.py - 真实 HTTP 端口探测与接口验证
"""

import sys
import os
import json
import time
import threading
import urllib.request
import unittest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INTERCEPTORS_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "interceptors")
sys.path.insert(0, INTERCEPTORS_DIR)

from model_adapter_gateway import ModelGatewayHandler
from http.server import HTTPServer

TEST_PORT = 50998

class TestModelAdapterHTTP(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.httpd = HTTPServer(("127.0.0.1", TEST_PORT), ModelGatewayHandler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def test_health_check(self):
        url = f"http://127.0.0.1:{TEST_PORT}/health"
        with urllib.request.urlopen(url, timeout=2) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data["ok"])
            self.assertIn("Antigravity Model Adapter Gateway", data["service"])

    def test_load_code_assist(self):
        url = f"http://127.0.0.1:{TEST_PORT}/v1internal:loadCodeAssist"
        req = urllib.request.Request(url, data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=2) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data["userStatus"], "ACTIVE")
            self.assertEqual(data["currentTier"], "TIER_PRO")

    def test_fetch_available_models_injected(self):
        url = f"http://127.0.0.1:{TEST_PORT}/v1internal:fetchAvailableModels"
        req = urllib.request.Request(url, data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=2) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            models = data.get("models", [])
            model_names = [m["name"] for m in models]

            # 验证 Google 默认模型和外接模型共存
            self.assertIn("models/gemini-2.5-pro", model_names)
            self.assertIn("models/gemini-2.5-flash", model_names)
            self.assertIn("models/deepseek-chat", model_names)
            self.assertIn("models/deepseek-reasoner", model_names)

            # 验证中文友好显示名称
            deepseek_model = next(m for m in models if m["name"] == "models/deepseek-chat")
            self.assertIn("DeepSeek V3", deepseek_model["displayName"])

if __name__ == "__main__":
    unittest.main()
