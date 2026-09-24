"""Integrity helpers for private pre-migration row snapshots."""

import hashlib
import json
from pathlib import Path


def digest_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(path):
    path = Path(path)
    manifest = path.with_suffix(path.suffix + ".sha256")
    manifest.write_text(f"{digest_file(path)}  {path.name}\n", encoding="ascii")
    return manifest


def verify_snapshot(path):
    path = Path(path)
    manifest = path.with_suffix(path.suffix + ".sha256")
    try:
        manifest_text = manifest.read_text(encoding="ascii").strip()
        expected, filename = manifest_text.split("  ", 1)
    except (OSError, ValueError):
        raise ValueError("Snapshot integrity manifest is missing or malformed.") from None
    if filename != path.name or len(expected) != 64:
        raise ValueError("Snapshot integrity manifest is invalid.")
    if not all(character in "0123456789abcdef" for character in expected):
        raise ValueError("Snapshot integrity manifest is invalid.")
    if digest_file(path) != expected:
        raise ValueError("Snapshot digest does not match its integrity manifest.")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("Snapshot JSON is unreadable or malformed.") from None
    if not isinstance(payload, dict) or payload.get("schema") != "vedioos":
        raise ValueError("Snapshot does not identify the expected private schema.")
    tables = payload.get("tables")
    if not isinstance(tables, dict) or not tables:
        raise ValueError("Snapshot has no table inventory.")
    for name, rows in tables.items():
        if not isinstance(name, str) or not name or not isinstance(rows, list):
            raise ValueError("Snapshot table data is malformed.")
        if any(not isinstance(row, dict) for row in rows):
            raise ValueError("Snapshot row data is malformed.")
    return payload
