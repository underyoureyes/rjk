"""Start the RJK server and open the browser."""
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

PORT = 8000
_ROOT = Path(__file__).parent


def _local_ip() -> str:
    """Best-effort: return the machine's LAN IP address."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def _wait_for_server(url: str, timeout: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:
            time.sleep(0.25)
    return False


if __name__ == "__main__":
    local_url = f"http://localhost:{PORT}"
    lan_ip    = _local_ip()
    lan_url   = f"http://{lan_ip}:{PORT}"

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app",
         "--host", "0.0.0.0", "--port", str(PORT), "--reload"],
        cwd=_ROOT,
    )
    print(f"Starting RJK …")
    if _wait_for_server(local_url):
        webbrowser.open(local_url)
        print()
        print(f"  Local:    {local_url}")
        print(f"  Network:  {lan_url}  ← share this with others on your LAN")
        print()
        print("Ctrl+C to stop")
    else:
        print("Server did not start in time — check for errors above.")
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
