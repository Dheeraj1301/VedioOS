from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from core.snapshot_integrity import verify_snapshot


class Command(BaseCommand):
    help = "Verify a private row snapshot's digest/structure and optionally compare live row counts."

    def add_arguments(self, parser):
        parser.add_argument("path", nargs="?")
        parser.add_argument("--against-database", action="store_true")

    def handle(self, *args, **options):
        directory = (settings.BASE_DIR / ".runtime").resolve()
        if options["path"]:
            path = Path(options["path"])
            if not path.is_absolute():
                path = settings.BASE_DIR / path
            path = path.resolve()
        else:
            candidates = sorted(directory.glob("database-snapshot-*.json"), reverse=True)
            candidates = [item for item in candidates if item.with_suffix(".json.sha256").exists()]
            if not candidates:
                raise CommandError("No snapshot with an integrity manifest was found.")
            path = candidates[0]
        if directory not in path.parents or path.suffix != ".json":
            raise CommandError("Snapshot must be a JSON file inside the ignored .runtime directory.")
        try:
            payload = verify_snapshot(path)
        except ValueError as exc:
            raise CommandError(str(exc)) from None
        tables = payload["tables"]
        row_count = sum(len(rows) for rows in tables.values())
        if options["against_database"]:
            if connection.vendor != "postgresql":
                raise CommandError("Live comparison requires PostgreSQL.")
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_schema()")
                if cursor.fetchone()[0] != "vedioos":
                    raise CommandError("Refusing to compare an unexpected schema.")
                cursor.execute(
                    "SELECT tablename FROM pg_tables WHERE schemaname=%s ORDER BY tablename",
                    ["vedioos"],
                )
                live_tables = [row[0] for row in cursor.fetchall()]
                if set(live_tables) != set(tables):
                    raise CommandError("Snapshot and live database table inventories differ.")
                for table in live_tables:
                    qualified = (
                        f"{connection.ops.quote_name('vedioos')}."
                        f"{connection.ops.quote_name(table)}"
                    )
                    cursor.execute(f"SELECT COUNT(*) FROM {qualified}")
                    if cursor.fetchone()[0] != len(tables[table]):
                        raise CommandError("Snapshot and live database row counts differ.")
        suffix = " and live row counts" if options["against_database"] else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"Verified {path.name}: {len(tables)} tables, {row_count} rows, digest/structure{suffix}."
            )
        )
