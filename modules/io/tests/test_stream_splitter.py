#!/usr/bin/env python3
"""
test_stream_splitter.py - Unit test for intercepting stream lines and publishing events.
"""
import unittest
import os
import sys
import io

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
IO_ROOT = os.path.dirname(TESTS_DIR)
sys.path.insert(0, os.path.join(IO_ROOT, "core_bus"))
sys.path.insert(0, os.path.join(IO_ROOT, "interceptors"))

from event_broker import EventBroker
import stream_splitter

class TestStreamSplitter(unittest.TestCase):
    def test_01_intercept_url_line(self):
        broker = EventBroker()
        events = []
        broker.register_handler("core.url.open", lambda ev: events.append(ev))

        raw_stream = io.StringIO(
            "Starting Antigravity core\n"
            "ANTIGRAVITY_OPEN_URL: https://accounts.google.com/o/oauth2/auth?client_id=123\n"
            "Normal log output\n"
        )
        out_stream = io.StringIO()

        lines, emitted = stream_splitter.process_stream(raw_stream, out_stream, broker)

        self.assertEqual(lines, 3)
        self.assertEqual(emitted, 1)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event"], "core.url.open")
        self.assertIn("https://accounts.google.com", events[0]["data"]["url"])
        self.assertEqual(out_stream.getvalue(), raw_stream.getvalue())

    def test_02_intercept_panic_error(self):
        broker = EventBroker()
        events = []
        broker.register_handler("system.error", lambda ev: events.append(ev))

        raw_stream = io.StringIO("panic: runtime error: invalid memory address\n")
        out_stream = io.StringIO()

        lines, emitted = stream_splitter.process_stream(raw_stream, out_stream, broker)

        self.assertEqual(lines, 1)
        self.assertEqual(emitted, 1)
        self.assertEqual(events[0]["event"], "system.error")
        self.assertIn("panic", events[0]["data"]["message"])

    def test_03_async_publishing_queue(self):
        import time
        broker = EventBroker()
        events = []

        def slow_handler(ev):
            time.sleep(0.05)
            events.append(ev)

        broker.register_handler("agent.*", slow_handler)

        raw_stream = io.StringIO(
            "line 1\n"
            "[task:start] 123 Initializing task\n"
            "line 2\n"
            "[task:done] 123 Task complete\n"
            "line 3\n"
        )
        out_stream = io.StringIO()

        start_t = time.time()
        lines, emitted = stream_splitter.process_stream(raw_stream, out_stream, broker)
        elapsed = time.time() - start_t

        self.assertEqual(lines, 5)
        self.assertEqual(emitted, 2)
        self.assertEqual(len(events), 2)
        self.assertEqual(out_stream.getvalue(), raw_stream.getvalue())

if __name__ == "__main__":
    unittest.main()
