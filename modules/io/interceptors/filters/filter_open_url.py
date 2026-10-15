#!/usr/bin/env python3
"""
filter_open_url.py - Inspects a stream line for browser URLs or OAuth flows.
Returns an Event Envelope dictionary if detected, or None.
"""
import re
from typing import Optional, Dict, Any

URL_REGEX = re.compile(r"https?://[\w\-\.\~:\?\#\[\]\@\!\$\&\'\(\)\*\+,;=%/]+")

def filter_line(line: str) -> Optional[Dict[str, Any]]:
    if not line:
        return None
    
    # Check explicit prefixes
    for prefix in ("AGY_OPEN_URL=", "ANTIGRAVITY_OPEN_URL:", "ANTIGRAVITY_OPEN_URL="):
        if prefix in line:
            url = line.split(prefix, 1)[1].strip()
            if url:
                return {
                    "event": "core.url.open",
                    "source": "language_server:stdout",
                    "data": {"url": url, "type": "explicit_prefix"}
                }
    
    # Check OAuth URLs
    if any(kw in line for kw in ("accounts.google.com", "oauth2", "/auth/callback")):
        m = URL_REGEX.search(line)
        if m:
            candidate = m.group(0)
            return {
                "event": "core.url.open",
                "source": "language_server:stdout",
                "data": {"url": candidate, "type": "oauth_pattern"}
            }
    
    return None
