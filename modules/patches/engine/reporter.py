"""
reporter.py - Builds structured JSON reports for patch operations.
"""
import time
from typing import Dict, Any, List

def build_report(
    core_path: str,
    sha256_initial: str,
    sha256_final: str,
    size: int,
    group_results: List[Dict[str, Any]],
    mode: Dict[str, bool],
    ok: bool
) -> Dict[str, Any]:
    return {
        "schema": 1,
        "core": {
            "path": core_path,
            "sha256_initial": sha256_initial,
            "sha256_final": sha256_final,
            "size": size
        },
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mode": mode,
        "ok": ok,
        "groups": group_results
    }
