"""Start the RJK server and open the browser."""
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

PORT = 8000

if __name__ == "__main__":
    url = f"http://localhost:{PORT}"
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app",
         "--host", "0.0.0.0", "--port", str(PORT), "--reload"],
        cwd=Path(__file__).parent,
    )
    time.sleep(1.5)
    webbrowser.open(url)
    print(f"RJK running at {url}  (Ctrl+C to stop)")
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
