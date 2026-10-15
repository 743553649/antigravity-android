#!/usr/bin/env python3
"""
probe_server.py - Probes the standalone core HTTP server until active or timeout.
"""
import sys
import time
import urllib.request
import urllib.error

def probe(port: int = 45159, timeout_sec: int = 20) -> bool:
    url = f"http://127.0.0.1:{port}"
    print(f"[*] Probing core server at {url} (timeout: {timeout_sec}s)...")
    start = time.time()

    while time.time() - start < timeout_sec:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AntigravityProbe/1.0"})
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                status = resp.status
                print(f"[OK] Server responded with HTTP status {status} in {time.time() - start:.2f}s!")
                return True
        except urllib.error.HTTPError as e:
            # An HTTP error (e.g. 401 Unauthorized or 404 Not Found) means the server is UP and responding!
            print(f"[OK] Server responded with HTTP {e.code} in {time.time() - start:.2f}s (Server is UP!)")
            return True
        except Exception:
            time.sleep(0.5)

    print(f"[FAIL] Server at {url} did not respond within {timeout_sec}s.", file=sys.stderr)
    return False

def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 45159
    timeout = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    ok = probe(port, timeout)
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
