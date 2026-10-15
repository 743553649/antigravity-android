"""
preflight.py - Rapid hardware, storage, and architecture preflight diagnostics.
"""
import os
import shutil
import platform
from typing import Dict, Any

def run_preflight(app_root: str = "/data/user/0/com.agy/files", min_mb_free: int = 250) -> Dict[str, Any]:
    arch = platform.machine().lower()
    is_aarch64 = arch in ("aarch64", "arm64")
    
    # Check free disk space
    free_mb = 0
    if os.path.exists(app_root):
        stat = shutil.disk_usage(app_root)
        free_mb = stat.free // (1024 * 1024)
    
    space_ok = free_mb >= min_mb_free
    write_ok = os.access(app_root, os.W_OK) if os.path.exists(app_root) else False

    ok = is_aarch64 and space_ok and write_ok

    return {
        "ok": ok,
        "arch": arch,
        "is_aarch64": is_aarch64,
        "free_disk_mb": free_mb,
        "space_ok": space_ok,
        "write_ok": write_ok,
        "app_root": app_root
    }
