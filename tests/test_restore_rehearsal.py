import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TransactionTestCase, override_settings

from core.models import Client, User
from core.snapshot_integrity import write_manifest

PASSWORD = "Synthetic-Restore-72!Leaf"


class RestoreRehearsalTests(TransactionTestCase):
    databases = {"default", "restore_rehearsal"}

    def export_test_database(self, directory):
        user = User.objects.create_user(
            "restore-client@example.test", PASSWORD, name="Restore Client"
        )
        Client.objects.create(user=user)
        tables = {}
        with connection.cursor() as cursor:
            names = sorted(connection.introspection.table_names(cursor))
            for table in names:
                cursor.execute(f"SELECT * FROM {connection.ops.quote_name(table)}")
                columns = [item[0] for item in cursor.description]
                tables[table] = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        runtime = Path(directory) / ".runtime"
        runtime.mkdir()
        path = runtime / "database-snapshot-20260924T120000000000Z.json"
        path.write_text(
            json.dumps({"schema": "vedioos", "tables": tables}, default=str), encoding="utf-8"
        )
        write_manifest(path)
        return path

    def test_snapshot_restores_only_into_disposable_database(self):
        with TemporaryDirectory() as directory:
            self.export_test_database(directory)
            before = User.objects.count()
            output = StringIO()
            with override_settings(BASE_DIR=Path(directory)):
                call_command("rehearse_database_restore", stdout=output)
            self.assertEqual(User.objects.count(), before)
            self.assertIn("foreign keys and integrity passed", output.getvalue())
            self.assertIn("No live database was modified", output.getvalue())
            self.assertFalse(list((Path(directory) / ".runtime").glob("restore-rehearsal-*")))

    def test_rehearsal_rejects_schema_drift_without_row_details(self):
        with TemporaryDirectory() as directory:
            path = self.export_test_database(directory)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["tables"].pop("projects")
            path.write_text(json.dumps(payload, default=str), encoding="utf-8")
            write_manifest(path)
            with override_settings(BASE_DIR=Path(directory)):
                with self.assertRaisesMessage(CommandError, "table inventory") as raised:
                    call_command("rehearse_database_restore")
            self.assertNotIn("restore-client@example.test", str(raised.exception))
