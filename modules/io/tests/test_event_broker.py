#!/usr/bin/env python3
"""
test_event_broker.py - Unit tests for EventBroker and SubscriberRouter.
"""
import unittest
import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
IO_ROOT = os.path.dirname(TESTS_DIR)
sys.path.insert(0, os.path.join(IO_ROOT, "core_bus"))

import envelope
from subscriber_router import SubscriberRouter
from event_broker import EventBroker

class TestEventBroker(unittest.TestCase):
    def test_01_router_wildcards(self):
        router = SubscriberRouter()
        router.subscribe("core.*", ["out1.sh"])
        router.subscribe("core.url.*", ["out2.sh"])
        router.subscribe("*", ["out3.sh"])

        dest1 = router.get_destinations("core.url.open")
        self.assertEqual(dest1, ["out1.sh", "out2.sh", "out3.sh"])

        dest2 = router.get_destinations("agent.task")
        self.assertEqual(dest2, ["out3.sh"])

    def test_02_broker_in_memory_dispatch(self):
        broker = EventBroker()
        received = []

        def my_handler(ev):
            received.append(ev["event"])

        broker.register_handler("agent.*", my_handler)
        
        # Publish matching
        ev1 = envelope.create_event("agent.started", "source")
        broker.publish(ev1)
        
        # Publish non-matching
        ev2 = envelope.create_event("system.boot", "source")
        broker.publish(ev2)

        self.assertEqual(received, ["agent.started"])

    def test_03_timeout_cleanup(self):
        import tempfile
        import time

        tmp_dir = tempfile.mkdtemp()
        try:
            hang_script = os.path.join(tmp_dir, "hang.py")
            with open(hang_script, "w") as f:
                f.write("import time\ntime.sleep(5)\n")

            broker = EventBroker(outputs_dir=tmp_dir, dispatch_timeout=0.2)
            broker.router.subscribe("test.timeout", ["hang.py"])

            ev = envelope.create_event("test.timeout", "test_source")
            t0 = time.time()
            dispatched = broker.publish(ev)
            elapsed = time.time() - t0

            # Should finish quickly after timeout (not 5s)
            self.assertLess(elapsed, 2.0)
            self.assertEqual(dispatched, [])
        finally:
            if os.path.exists(hang_script):
                os.remove(hang_script)
            os.rmdir(tmp_dir)

if __name__ == "__main__":
    unittest.main()
