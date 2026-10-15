"""
client.py - Lightweight IPC client sending command envelopes to the Android System Gateway.
"""
import json
import os
import urllib.request
import urllib.error
from typing import Dict, Any

def resolve_gateway_url() -> str:
    if "AGY_GATEWAY_URL" in os.environ:
        return os.environ["AGY_GATEWAY_URL"]
    for pfile in [
        "/data/user/0/com.agy.dev/files/logs/gateway.port",
        "/data/user/0/com.agy/files/logs/gateway.port"
    ]:
        if os.path.isfile(pfile):
            try:
                with open(pfile, "r") as f:
                    p = f.read().strip()
                    if p.isdigit():
                        return f"http://127.0.0.1:{p}/gateway"
            except Exception:
                pass
    return "http://127.0.0.1:45161/gateway" if os.environ.get("DEV_MODE") == "1" else "http://127.0.0.1:45160/gateway"

DEFAULT_GATEWAY_URL = resolve_gateway_url()

def send_command(command: str, payload: Dict[str, Any] = None, gateway_url: str = None) -> Dict[str, Any]:
    url = gateway_url or resolve_gateway_url()
    packet = {
        "command": command,
        "payload": payload or {}
    }
    data = json.dumps(packet).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    
    try:
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError) as e:
        # If default url was used, try the alternate port (45160 <-> 45161)
        if gateway_url is None:
            alt_url = "http://127.0.0.1:45160/gateway" if ":45161/" in url else "http://127.0.0.1:45161/gateway"
            try:
                alt_req = urllib.request.Request(alt_url, data=data, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(alt_req, timeout=1.0) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except Exception:
                pass
        return {"ok": False, "fallback": True, "error": str(e), "packet": packet}
