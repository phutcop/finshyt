"""Start the Finshyt demo as detached localhost services.

Run from any directory with: python3 start_local.py
Logs and process IDs are kept in .local-run beside this file.
"""

from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parent
RUN_DIR = ROOT / ".local-run"
RUN_DIR.mkdir(exist_ok=True)


def responds(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return 200 <= response.status < 400
    except (OSError, urllib.error.URLError):
        return False


def launch(name: str, command: list[str], cwd: Path) -> None:
    log_path = RUN_DIR / f"{name}.log"
    with log_path.open("ab") as log:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    (RUN_DIR / f"{name}.pid").write_text(str(process.pid))


backend_url = "http://127.0.0.1:8001/health"
frontend_url = "http://127.0.0.1:5174/"

if not responds(backend_url):
    launch(
        "backend",
        [str(ROOT / "backend/.venv/bin/python"), "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8001"],
        ROOT / "backend",
    )

if not responds(frontend_url):
    launch(
        "frontend",
        ["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", "5174"],
        ROOT / "frontend",
    )

for _ in range(30):
    if responds(backend_url) and responds(frontend_url):
        print(f"Finshyt ready: {frontend_url}")
        print(f"API ready: {backend_url}")
        break
    time.sleep(0.2)
else:
    raise SystemExit(f"Startup failed. Check logs in {RUN_DIR}")
