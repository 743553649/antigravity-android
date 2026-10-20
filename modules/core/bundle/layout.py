#!/usr/bin/env python3
"""
layout.py - Layout specifications and directory structure for runtime assets.
"""
import os

SUBDIRS = ("bin", "lib", "certs", "seed", "etc")

def create_layout(base_out_dir: str) -> dict:
    paths = {}
    for sub in SUBDIRS:
        d = os.path.join(base_out_dir, sub)
        os.makedirs(d, exist_ok=True)
        paths[sub] = d
    return paths
