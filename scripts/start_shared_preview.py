"""Verify the shared Supabase binding, then start the team preview.

This is deliberately separate from the offline ``vedioos.local_settings`` flow.
It exits before starting Django when the environment points at SQLite, another
Supabase project, the wrong schema, mismatched Auth, or pending migrations.
"""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANAGE = ROOT / "manage.py"


def run_manage(*arguments):
    return subprocess.run(
        [sys.executable, str(MANAGE), *arguments],
        cwd=ROOT,
        check=True,
    )


def main():
    parser = argparse.ArgumentParser(description="Start a verified shared Supabase preview.")
    parser.add_argument("--address", default="127.0.0.1:8000")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Verify the shared binding without starting the server.",
    )
    args = parser.parse_args()

    run_manage("check_shared_preview")
    run_manage("check_database")
    if not args.check_only:
        run_manage("runserver", args.address, "--noreload")


if __name__ == "__main__":
    main()
