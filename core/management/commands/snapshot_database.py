"""Local, consistent row export before additive migrations. Contains private data."""

import json
from datetime import datetime, timezone

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from core.snapshot_integrity import write_manifest


class Command(BaseCommand):
    help = "Save a consistent private-schema row snapshot in ignored .runtime before migrations."

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            raise CommandError(
                "Use a SQLite file backup for local development; this command is for PostgreSQL."
            )
        snapshot = {}
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            cursor.execute("SELECT current_schema()")
            schema = cursor.fetchone()[0]
            if schema != "vedioos":
                raise CommandError("Refusing to export an unexpected schema.")
            cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname=%s ORDER BY tablename", [schema])
            tables = [row[0] for row in cursor.fetchall()]
            for table in tables:
                qualified = f"{connection.ops.quote_name(schema)}.{connection.ops.quote_name(table)}"
                cursor.execute(f"SELECT row_to_json(t) FROM {qualified} t")
                snapshot[table] = [row[0] for row in cursor.fetchall()]
        directory = settings.BASE_DIR / ".runtime"
        directory.mkdir(exist_ok=True)
        path = directory / f"database-snapshot-{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}.json"
        with path.open("x", encoding="utf-8") as stream:
            json.dump({"schema": schema, "tables": snapshot}, stream, default=str)
        manifest = write_manifest(path)
        self.stdout.write(
            f"Saved private row snapshot: {path.name}; {len(tables)} tables; integrity manifest: "
            f"{manifest.name}. Keep both ignored files private. This is not a full database/role backup."
        )
