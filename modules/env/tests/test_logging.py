#!/usr/bin/env python3
"""
test_logging.py - Unit tests for structured logger and crash flight recorder.
"""
import unittest
import os
import sys
import tempfile
import shutil
import json

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_ROOT = os.path.dirname(TESTS_DIR)
sys.path.insert(0, os.path.join(ENV_ROOT, "logging"))

import log
import flight_recorder

class TestLogging(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_01_structured_log_jsonl(self):
        log_file = os.path.join(self.tmp_dir, "test_log.jsonl")
        log.log("INFO", "TEST", "Testing message", meta={"step": 1}, jsonl_file=log_file)
        
        self.assertTrue(os.path.isfile(log_file))
        with open(log_file, "r", encoding="utf-8") as f:
            line = f.readline()
            data = json.loads(line)
            self.assertEqual(data["level"], "INFO")
            self.assertEqual(data["tag"], "TEST")
            self.assertEqual(data["msg"], "Testing message")
            self.assertEqual(data["meta"]["step"], 1)

    def test_02_flight_recorder(self):
        dump_file = os.path.join(self.tmp_dir, "crash_snapshot.json")
        out = flight_recorder.record_crash_snapshot("Fatal test error", dump_file, {"culprit": "test"})
        self.assertEqual(out, os.path.abspath(dump_file))
        self.assertTrue(os.path.isfile(out))
        with open(out, "r", encoding="utf-8") as f:
            snap = json.load(f)
            self.assertEqual(snap["error"], "Fatal test error")
            self.assertEqual(snap["extra_context"]["culprit"], "test")

if __name__ == "__main__":
    unittest.main()
