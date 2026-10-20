#!/usr/bin/env python3
"""
event_broker.py - Central event broker that accepts events and dispatches them to output handlers.
"""
import os
import sys
import subprocess
from typing import Dict, Any, List

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
IO_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)

import envelope
from subscriber_router import SubscriberRouter

class EventBroker:
    def __init__(self, routes_path: str = None, outputs_dir: str = None, dispatch_timeout: float = 5.0):
        self.outputs_dir = outputs_path = outputs_dir or os.path.join(IO_ROOT, "outputs")
        routes_file = routes_path or os.path.join(IO_ROOT, "spec", "default_routes.json")
        self.router = SubscriberRouter(routes_file)
        self.in_memory_handlers = {}
        self.dispatch_timeout = dispatch_timeout

    def register_handler(self, pattern: str, handler_callable):
        if pattern not in self.in_memory_handlers:
            self.in_memory_handlers[pattern] = []
        self.in_memory_handlers[pattern].append(handler_callable)

    def publish(self, event_dict: Dict[str, Any], timeout: float = None) -> List[str]:
        envelope.validate_event(event_dict)
        event_name = event_dict["event"]
        dispatched_to = []
        effective_timeout = timeout if timeout is not None else self.dispatch_timeout

        # 1. In-memory handlers
        for pattern, handlers in self.in_memory_handlers.items():
            from fnmatch import fnmatch
            if fnmatch(event_name, pattern):
                for h in handlers:
                    try:
                        h(event_dict)
                        dispatched_to.append(f"handler:{h.__name__}")
                    except Exception as e:
                        print(f"[EventBroker] Error in handler {h}: {e}", file=sys.stderr)

        # 2. Output scripts
        destinations = self.router.get_destinations(event_name)
        raw_json = envelope.serialize_event(event_dict)

        for dest_script_name in destinations:
            script_path = os.path.join(self.outputs_dir, dest_script_name)
            if not os.path.isfile(script_path):
                continue
            
            proc = None
            try:
                # Dispatch script: on Android /storage/emulated/0 is mounted noexec,
                # so shell scripts must be explicitly invoked via /system/bin/sh or bash.
                if script_path.endswith(".sh"):
                    sh_bin = "/system/bin/sh" if os.path.isfile("/system/bin/sh") else "bash"
                    cmd = [sh_bin, script_path]
                else:
                    cmd = [sys.executable, script_path]

                proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True
                )
                proc.communicate(input=raw_json + "\n", timeout=effective_timeout)
                dispatched_to.append(dest_script_name)
            except subprocess.TimeoutExpired as e:
                print(f"[EventBroker] Timeout dispatching to {dest_script_name}: {e}", file=sys.stderr)
                if proc is not None:
                    try:
                        proc.kill()
                    except OSError:
                        pass
                    try:
                        proc.wait()
                    except OSError:
                        pass
                    if proc.stdin and not proc.stdin.closed:
                        try:
                            proc.stdin.close()
                        except OSError:
                            pass
                    if proc.stderr and not proc.stderr.closed:
                        try:
                            proc.stderr.close()
                        except OSError:
                            pass
            except Exception as e:
                print(f"[EventBroker] Error dispatching to {dest_script_name}: {e}", file=sys.stderr)
                if proc is not None and proc.poll() is None:
                    try:
                        proc.kill()
                        proc.wait()
                    except OSError:
                        pass

        return dispatched_to
