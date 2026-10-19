"""Verify the shared Supabase and private-storage bindings, then start the team preview.

This is deliberately separate from the offline ``vedioos.local_settings`` flow.
It exits before starting Django when the environment points at SQLite, another
Supabase project, the wrong schema, mismatched Auth, or pending migrations.
"""

import argparse
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
MANAGE = ROOT / "manage.py"
STORAGE_SCRIPT = ROOT / "scripts" / "start_storage.py"
STORAGE_LOG = ROOT / ".runtime" / "storage-preview.log"


def run_manage(*arguments):
    return subprocess.run(
        [sys.executable, str(MANAGE), *arguments],
        cwd=ROOT,
        check=True,
    )


def _local_storage_address():
    endpoint = urlparse(os.environ.get("S3_ENDPOINT_URL", ""))
    if endpoint.scheme not in {"http", "https"} or endpoint.hostname not in {
        "127.0.0.1",
        "localhost",
        "::1",
    }:
        return None
    return endpoint.hostname, endpoint.port or (443 if endpoint.scheme == "https" else 80)


def _port_is_open(address):
    try:
        with socket.create_connection(address, timeout=1):
            return True
    except OSError:
        return False


def ensure_local_storage():
    """Start the repository's loopback storage when the shared preview needs it."""
    address = _local_storage_address()
    if address is None or _port_is_open(address):
        return None

    STORAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
    log = STORAGE_LOG.open("a", encoding="utf-8")
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    process = subprocess.Popen(
        [sys.executable, str(STORAGE_SCRIPT)],
        cwd=ROOT,
        stdout=log,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )
    process._vedioos_log = log
    try:
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(
                    f"Local private storage exited during startup. See {STORAGE_LOG}."
                )
            if _port_is_open(address):
                # The S3 listener opens before its internal services elect a leader.
                time.sleep(2)
                run_manage("init_storage")
                return process
            time.sleep(0.5)
        raise RuntimeError(
            f"Local private storage did not become ready. See {STORAGE_LOG}."
        )
    except BaseException:
        stop_local_storage(process)
        raise


def stop_local_storage(process):
    if process is None:
        return
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    process._vedioos_log.close()


def main():
    # This developer-only launcher intentionally uses the repository's private
    # shared-preview configuration instead of unrelated inherited shell values.
    load_dotenv(ROOT / ".env", override=True)

    parser = argparse.ArgumentParser(description="Start a verified shared Supabase preview.")
    parser.add_argument("--address", default="127.0.0.1:8000")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Verify the shared binding without starting the server.",
    )
    args = parser.parse_args()

    storage_process = None
    try:
        run_manage("check_shared_preview")
        run_manage("check_database")
        run_manage("verify_cloud")
        storage_process = ensure_local_storage()
        run_manage("check_private_storage")
        if not args.check_only:
            run_manage("runserver", args.address, "--noreload")
    finally:
        stop_local_storage(storage_process)


if __name__ == "__main__":
    main()
