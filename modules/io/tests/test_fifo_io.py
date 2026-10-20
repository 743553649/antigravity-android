#!/usr/bin/env python3
"""
test_fifo_io.py - Unit test for FIFO pipe input and EventBroker integration.
"""
import unittest
import os
import sys
import tempfile
import threading
import time

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
IO_ROOT = os.path.dirname(TESTS_DIR)
sys.path.insert(0, os.path.join(IO_ROOT, "core_bus"))
sys.path.insert(0, os.path.join(IO_ROOT, "inputs"))

import envelope
import fifo_input
from event_broker import EventBroker

class TestFifoIO(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.fifo_path = os.path.join(self.tmp_dir, "test.pipe")

    def tearDown(self):
        if os.path.exists(self.fifo_path):
            os.remove(self.fifo_path)
        os.rmdir(self.tmp_dir)

    def test_01_fifo_event_flow(self):
        broker = EventBroker()
        received = []
        broker.register_handler("test.*", lambda ev: received.append(ev))

        # Run listener in background thread
        listener_thread = threading.Thread(
            target=fifo_input.run_fifo_listener,
            args=(self.fifo_path, broker, 1),
            daemon=True
        )
        listener_thread.start()
        time.sleep(0.1)

        # Write event to FIFO
        ev = envelope.create_event("test.fifo_event", "test_writer", {"data": 123})
        with open(self.fifo_path, "w", encoding="utf-8") as f:
            f.write(envelope.serialize_event(ev) + "\n")

        listener_thread.join(timeout=2.0)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["event"], "test.fifo_event")
        self.assertEqual(received[0]["data"]["data"], 123)

    def test_02_fuse_path_redirection(self):
        fuse_path = "/storage/emulated/0/Documents/test_fuse.pipe"
        safe_path = fifo_input.get_safe_pipe_path(fuse_path)
        self.assertFalse(safe_path.startswith("/storage/"))
        self.assertTrue(safe_path.endswith("test_fuse.pipe"))

    def test_03_nonblocking_write_no_reader(self):
        # Create fifo without reader
        if not os.path.exists(self.fifo_path):
            os.mkfifo(self.fifo_path)
        # Writing should return False immediately without hanging
        t0 = time.time()
        res = fifo_input.write_fifo_nonblocking(self.fifo_path, '{"event":"test"}')
        elapsed = time.time() - t0
        self.assertFalse(res)
        self.assertLess(elapsed, 0.5)

    def test_04_nonblocking_write_with_reader(self):
        broker = EventBroker()
        received = []
        broker.register_handler("test.*", lambda ev: received.append(ev))

        listener_thread = threading.Thread(
            target=fifo_input.run_fifo_listener,
            args=(self.fifo_path, broker, 1),
            daemon=True
        )
        listener_thread.start()
        time.sleep(0.1)

        ev = envelope.create_event("test.nonblocking", "test_source", {"msg": "ok"})
        success = fifo_input.write_fifo_nonblocking(self.fifo_path, envelope.serialize_event(ev))
        self.assertTrue(success)

        listener_thread.join(timeout=2.0)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["event"], "test.nonblocking")
        self.assertEqual(received[0]["data"]["msg"], "ok")

if __name__ == "__main__":
    unittest.main()
