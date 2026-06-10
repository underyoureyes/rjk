"""Start the RJK server and open the browser."""
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

PORT = 8000
_ROOT = Path(__file__).parent


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
    url = f"http://localhost:{PORT}"
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app",
         "--host", "0.0.0.0", "--port", str(PORT), "--reload"],
        cwd=_ROOT,
    )
    print(f"Starting RJK on {url} …")
    if _wait_for_server(url):
        webbrowser.open(url)
        print(f"RJK running at {url}  (Ctrl+C to stop)")
    else:
        print("Server did not start in time — check for errors above.")
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
