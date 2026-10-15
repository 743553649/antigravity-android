#!/usr/bin/env python3
"""
test_envelope.py - Unit tests for event envelope serialization and validation.
"""
import unittest
import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
IO_ROOT = os.path.dirname(TESTS_DIR)
sys.path.insert(0, os.path.join(IO_ROOT, "core_bus"))

import envelope

class TestEnvelope(unittest.TestCase):
    def test_01_create_valid_event(self):
        ev = envelope.create_event("core.test.event", "test_source", {"key": "value"})
        self.assertEqual(ev["event"], "core.test.event")
        self.assertEqual(ev["source"], "test_source")
        self.assertEqual(ev["data"]["key"], "value")
        self.assertIsInstance(ev["timestamp"], int)

    def test_02_serialization_roundtrip(self):
        ev = envelope.create_event("agent.started", "hub", {"agent_id": 42})
        serialized = envelope.serialize_event(ev)
        deserialized = envelope.deserialize_event(serialized)
        self.assertEqual(deserialized["event"], ev["event"])
        self.assertEqual(deserialized["data"]["agent_id"], 42)

    def test_03_invalid_envelopes(self):
        with self.assertRaises(ValueError):
            envelope.create_event("", "source")
        with self.assertRaises(ValueError):
            envelope.deserialize_event('{"event": "test"}')

if __name__ == "__main__":
    unittest.main()
