from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.restore_rehearsal import rehearse_snapshot
from core.snapshot_integrity import verify_snapshot


class Command(BaseCommand):
    help = "Restore a manifested row snapshot into a disposable SQLite database and validate it."

    def add_arguments(self, parser):
        parser.add_argument("path", nargs="?")

    def handle(self, *args, **options):
        runtime = (settings.BASE_DIR / ".runtime").resolve()
        if options["path"]:
            path = Path(options["path"])
            if not path.is_absolute():
                path = settings.BASE_DIR / path
            path = path.resolve()
        else:
            candidates = sorted(runtime.glob("database-snapshot-*.json"), reverse=True)
            candidates = [item for item in candidates if item.with_suffix(".json.sha256").exists()]
            if not candidates:
                raise CommandError("No snapshot with an integrity manifest was found.")
            path = candidates[0]
        if runtime not in path.parents or path.suffix != ".json":
            raise CommandError("Snapshot must be a JSON file inside the ignored .runtime directory.")
        try:
            payload = verify_snapshot(path)
            with TemporaryDirectory(prefix="restore-rehearsal-", dir=runtime) as directory:
                tables, rows = rehearse_snapshot(payload, Path(directory) / "restored.sqlite3")
        except (OSError, ValueError) as exc:
            raise CommandError(str(exc)) from None
        self.stdout.write(
            self.style.SUCCESS(
                f"Rehearsed {path.name}: restored {tables} tables / {rows} rows into an isolated "
                "temporary database; migrations, foreign keys and integrity passed. No live database "
                "was modified."
            )
        )
