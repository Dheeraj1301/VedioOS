"""Isolated SQLite rehearsal for private PostgreSQL row snapshots."""

import json
from pathlib import Path

from django.core.management import call_command
from django.db import connections
from django.db.migrations.executor import MigrationExecutor


def _sqlite_value(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, separators=(",", ":"), sort_keys=True)
    if isinstance(value, bool):
        return int(value)
    return value


def rehearse_snapshot(payload, target_path, alias="restore_rehearsal"):
    """Restore rows into a disposable migrated database and validate it."""
    target_path = Path(target_path)
    previous_config = connections.databases.get(alias)
    connections.databases[alias] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": target_path,
        "ATOMIC_REQUESTS": False,
        "AUTOCOMMIT": True,
        "CONN_MAX_AGE": 0,
        "CONN_HEALTH_CHECKS": False,
        "OPTIONS": {},
        "TIME_ZONE": None,
        "TEST": {},
        "USER": "",
        "PASSWORD": "",
        "HOST": "",
        "PORT": "",
    }
    database = connections[alias]
    try:
        call_command("migrate", database=alias, interactive=False, verbosity=0)
        with database.cursor() as cursor:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            target_tables = {row[0] for row in cursor.fetchall()}
            snapshot_tables = set(payload["tables"])
            if target_tables != snapshot_tables:
                raise ValueError("Snapshot table inventory does not match the migrated application schema.")

            cursor.execute("PRAGMA foreign_keys=OFF")
            for table in sorted(target_tables):
                cursor.execute(f"DELETE FROM {database.ops.quote_name(table)}")
            for table in sorted(snapshot_tables):
                cursor.execute(f"PRAGMA table_info({database.ops.quote_name(table)})")
                target_columns = {row[1] for row in cursor.fetchall()}
                rows = payload["tables"][table]
                for row in rows:
                    if set(row) != target_columns:
                        raise ValueError(f"Snapshot columns do not match the migrated schema for {table}.")
                    columns = list(row)
                    names = ", ".join(database.ops.quote_name(column) for column in columns)
                    placeholders = ", ".join(["%s"] * len(columns))
                    values = [_sqlite_value(row[column]) for column in columns]
                    cursor.execute(
                        f"INSERT INTO {database.ops.quote_name(table)} ({names}) "
                        f"VALUES ({placeholders})",
                        values,
                    )
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA foreign_key_check")
            if cursor.fetchone() is not None:
                raise ValueError("Restored rows fail foreign-key validation.")
            cursor.execute("PRAGMA integrity_check")
            if cursor.fetchone()[0] != "ok":
                raise ValueError("Restored database fails SQLite integrity validation.")

        executor = MigrationExecutor(database)
        if executor.migration_plan(executor.loader.graph.leaf_nodes()):
            raise ValueError("Restored migration history is not current.")
        return len(snapshot_tables), sum(len(rows) for rows in payload["tables"].values())
    finally:
        database.close()
        if previous_config is None:
            connections.databases.pop(alias, None)
        else:
            connections.databases[alias] = previous_config
        try:
            delattr(connections._connections, alias)
        except AttributeError:
            pass
