"""
port_checker.py - Validates availability of loopback TCP ports (e.g. 45157, 45158, 45159).
"""
import socket
from typing import Dict, Any

def check_port_available(port: int, host: str = "127.0.0.1") -> Dict[str, Any]:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            s.bind((host, port))
            return {"port": port, "available": True, "error": None}
        except OSError as e:
            return {"port": port, "available": False, "error": str(e)}
