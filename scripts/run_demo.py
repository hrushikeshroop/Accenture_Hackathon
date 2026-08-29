from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the ControlPlane.ai local demo.")
    parser.add_argument(
        "--smoke-test-seconds",
        type=float,
        default=None,
        help="Stop both services automatically after the supplied test duration.",
    )
    parser.add_argument(
        "--fresh-db",
        action="store_true",
        help=(
            "Use an isolated temporary audit database for a reproducible demo run. "
            "The audit remains available until both services stop."
        ),
    )
    args = parser.parse_args()
    temporary_database = (
        tempfile.TemporaryDirectory(prefix="controlplane-demo-")
        if args.fresh_db
        else None
    )
    child_environment = os.environ.copy()
    if temporary_database is not None:
        child_environment["CONTROLPLANE_DB_PATH"] = str(
            Path(temporary_database.name) / "controlplane-demo.db"
        )
    commands = [
        [
            sys.executable,
            "-m",
            "uvicorn",
            "controlplane.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "dashboard/app.py",
            "--server.headless=true",
            "--server.address=127.0.0.1",
            "--browser.gatherUsageStats=false",
        ],
    ]
    processes: list[subprocess.Popen[bytes]] = []
    requested_stop = False
    deadline = (
        time.monotonic() + args.smoke_test_seconds
        if args.smoke_test_seconds is not None
        else None
    )
    try:
        for command in commands:
            processes.append(
                subprocess.Popen(command, cwd=PROJECT_ROOT, env=child_environment)
            )
        print("ControlPlane API: http://127.0.0.1:8000/docs")
        print("The Streamlit URL will appear below. Press Ctrl+C to stop both services.")
        while all(process.poll() is None for process in processes):
            if deadline is not None and time.monotonic() >= deadline:
                requested_stop = True
                break
            time.sleep(0.25)
    except KeyboardInterrupt:
        requested_stop = True
    finally:
        for process in reversed(processes):
            stop_process(process)
        if temporary_database is not None:
            temporary_database.cleanup()

    failed = [process.returncode for process in processes if process.returncode]
    if failed and not requested_stop:
        raise SystemExit(f"A demo process exited unexpectedly: {failed}")


if __name__ == "__main__":
    main()
