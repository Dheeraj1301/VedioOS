import base64
import hashlib
import json
import tempfile
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from botocore.exceptions import ClientError
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from core.models import Client, File, Project, User
from operations.models import AuditLog


class StorageRecoveryTests(TestCase):
    def setUp(self):
        self.payload = b"verified recovered bytes"
        self.user = User.objects.create_user(
            "storage-recovery@example.test", "Synthetic-Recovery-72!Leaf", name="Client"
        )
        project = Project.objects.create(
            client=Client.objects.create(user=self.user), title="Recovery"
        )
        self.file = File.objects.create(
            project=project,
            uploader=self.user,
            filename="private-name.mp4",
            object_key="private/object.mp4",
            storage_version="missing-version",
            content_type="video/mp4",
            size_bytes=len(self.payload),
            sha256=hashlib.sha256(self.payload).hexdigest(),
            category="source",
            state="ready",
            expires_at="2030-01-01T00:00:00Z",
        )
        Path(settings.BASE_DIR, ".runtime").mkdir(exist_ok=True)

    def manifest(self, directory, payload=None):
        source = Path(directory, "recovered.bin")
        source.write_bytes(self.payload if payload is None else payload)
        manifest = Path(directory, "recovery.json")
        manifest.write_text(
            json.dumps({"files": [{"file_id": str(self.file.pk), "path": str(source)}]}),
            encoding="utf-8",
        )
        return manifest

    def test_dry_run_validates_bytes_without_storage_write(self):
        with tempfile.TemporaryDirectory(dir=Path(settings.BASE_DIR, ".runtime")) as directory:
            output = StringIO()
            call_command("restore_missing_storage_objects", self.manifest(directory), stdout=output)
        self.assertIn("dry run passed for 1 file", output.getvalue())
        self.file.refresh_from_db()
        self.assertEqual(self.file.storage_version, "missing-version")

    def test_dry_run_rejects_checksum_mismatch(self):
        with tempfile.TemporaryDirectory(dir=Path(settings.BASE_DIR, ".runtime")) as directory:
            with self.assertRaisesMessage(CommandError, "do not match"):
                call_command(
                    "restore_missing_storage_objects",
                    self.manifest(directory, b"changed"),
                )

    @override_settings(S3_BUCKET="private-media")
    def test_apply_uploads_verifies_and_audits_without_printing_identifiers(self):
        checksum = base64.b64encode(hashlib.sha256(self.payload).digest()).decode("ascii")
        client = SimpleNamespace()
        missing = ClientError(
            {"Error": {"Code": "NoSuchVersion", "Message": "missing"}},
            "HeadObject",
        )
        client.head_object = lambda **kwargs: (
            (_ for _ in ()).throw(missing)
            if kwargs.get("VersionId") == "missing-version"
            else {"ContentLength": len(self.payload), "ChecksumSHA256": checksum}
        )
        client.put_object = lambda **kwargs: {"VersionId": "restored-version"}
        with tempfile.TemporaryDirectory(dir=Path(settings.BASE_DIR, ".runtime")) as directory:
            output = StringIO()
            with patch(
                "core.management.commands.restore_missing_storage_objects.storage_client",
                return_value=client,
            ):
                call_command(
                    "restore_missing_storage_objects",
                    self.manifest(directory),
                    apply=True,
                    confirm_restore=True,
                    stdout=output,
                )
        self.file.refresh_from_db()
        self.assertEqual(self.file.storage_version, "restored-version")
        self.assertTrue(
            AuditLog.objects.filter(
                action="file.storage_recovered", target_id=str(self.file.pk), actor__isnull=True
            ).exists()
        )
        self.assertNotIn("private-name", output.getvalue())
        self.assertNotIn("private/object", output.getvalue())

    def test_apply_requires_both_confirmation_flags(self):
        with tempfile.TemporaryDirectory(dir=Path(settings.BASE_DIR, ".runtime")) as directory:
            with self.assertRaisesMessage(CommandError, "requires"):
                call_command(
                    "restore_missing_storage_objects",
                    self.manifest(directory),
                    apply=True,
                )

    @override_settings(S3_BUCKET="private-media")
    def test_apply_does_not_treat_provider_denial_as_a_missing_object(self):
        denied = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "denied"}},
            "HeadObject",
        )
        client = SimpleNamespace(
            head_object=lambda **kwargs: (_ for _ in ()).throw(denied),
            put_object=lambda **kwargs: self.fail("upload must not be attempted"),
        )
        with tempfile.TemporaryDirectory(dir=Path(settings.BASE_DIR, ".runtime")) as directory:
            with (
                patch(
                    "core.management.commands.restore_missing_storage_objects.storage_client",
                    return_value=client,
                ),
                self.assertRaisesMessage(CommandError, "could not verify"),
            ):
                call_command(
                    "restore_missing_storage_objects",
                    self.manifest(directory),
                    apply=True,
                    confirm_restore=True,
                )
