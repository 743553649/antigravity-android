"""
flight_recorder.py - Emergency post-mortem crash snapshot generator.
"""
import os
import sys
import json
import time
import shutil
import platform
from typing import Dict, Any

def record_crash_snapshot(error_msg: str, dump_path: str, extra_context: Dict[str, Any] = None) -> str:
    snapshot = {
        "timestamp": int(time.time() * 1000),
        "iso_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "error": error_msg,
        "platform": platform.platform(),
        "arch": platform.machine(),
        "python": sys.version,
        "pid": os.getpid(),
        "extra_context": extra_context or {}
    }
    try:
        snapshot["disk"] = shutil.disk_usage(os.getcwd())._asdict()
    except Exception:
        pass

    out_file = os.path.abspath(dump_path)
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)
        f.write("\n")
    return out_file
