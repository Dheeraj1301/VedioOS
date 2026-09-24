import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from core.snapshot_integrity import verify_snapshot, write_manifest


class SnapshotIntegrityTests(SimpleTestCase):
    def write_snapshot(self, directory, payload=None):
        runtime = Path(directory) / ".runtime"
        runtime.mkdir()
        path = runtime / "database-snapshot-20260924T000000000000Z.json"
        path.write_text(
            json.dumps(
                payload
                or {
                    "schema": "vedioos",
                    "tables": {"users": [{"id": "synthetic"}], "projects": []},
                }
            ),
            encoding="utf-8",
        )
        write_manifest(path)
        return path

    def test_manifest_and_snapshot_structure_verify(self):
        with TemporaryDirectory() as directory:
            path = self.write_snapshot(directory)
            payload = verify_snapshot(path)
            self.assertEqual(set(payload["tables"]), {"users", "projects"})

    def test_tampering_is_rejected_without_rendering_private_rows(self):
        with TemporaryDirectory() as directory:
            path = self.write_snapshot(directory)
            path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
            with self.assertRaisesMessage(ValueError, "digest does not match") as raised:
                verify_snapshot(path)
            self.assertNotIn("synthetic", str(raised.exception))

    def test_command_finds_latest_manifested_snapshot(self):
        with TemporaryDirectory() as directory:
            path = self.write_snapshot(directory)
            output = StringIO()
            with override_settings(BASE_DIR=Path(directory)):
                call_command("verify_database_snapshot", stdout=output)
            self.assertIn(path.name, output.getvalue())
            self.assertIn("2 tables, 1 rows", output.getvalue())

    def test_command_rejects_paths_outside_private_runtime(self):
        with TemporaryDirectory() as directory:
            outside = Path(directory) / "outside.json"
            outside.write_text("{}", encoding="utf-8")
            with override_settings(BASE_DIR=Path(directory)):
                with self.assertRaisesMessage(CommandError, "inside the ignored .runtime"):
                    call_command("verify_database_snapshot", str(outside))
