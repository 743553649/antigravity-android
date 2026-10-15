#!/usr/bin/env python3
"""
subscriber_router.py - Matches event names to subscriber output endpoints based on wildcard patterns.
"""
import fnmatch
import json
import os
from typing import List, Dict

class SubscriberRouter:
    def __init__(self, routes_file: str = None):
        self.routes: Dict[str, List[str]] = {}
        if routes_file and os.path.isfile(routes_file):
            self.load_routes(routes_file)

    def load_routes(self, routes_file: str) -> None:
        with open(routes_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            for r in data.get("routes", []):
                pattern = r.get("pattern")
                outputs = r.get("outputs", [])
                if pattern:
                    self.subscribe(pattern, outputs)

    def subscribe(self, pattern: str, outputs: List[str]) -> None:
        if pattern not in self.routes:
            self.routes[pattern] = []
        for out in outputs:
            if out not in self.routes[pattern]:
                self.routes[pattern].append(out)

    def get_destinations(self, event_type: str) -> List[str]:
        destinations = set()
        for pattern, outputs in self.routes.items():
            if fnmatch.fnmatch(event_type, pattern):
                destinations.update(outputs)
        return sorted(list(destinations))
