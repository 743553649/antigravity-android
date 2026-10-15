#!/usr/bin/env python3
"""
filter_error_alerts.py - Detects fatal errors, crash panics, or critical warnings.
"""
from typing import Optional, Dict, Any

def filter_line(line: str) -> Optional[Dict[str, Any]]:
    if not line:
        return None
    
    line_lower = line.lower()
    if "panic:" in line_lower or "fatal error:" in line_lower or "sigsegv" in line_lower or "sigill" in line_lower:
        return {
            "event": "system.error",
            "source": "language_server:stderr",
            "data": {"message": line.strip(), "severity": "fatal"}
        }
    
    return None
