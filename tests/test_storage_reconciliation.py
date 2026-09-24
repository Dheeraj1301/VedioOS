import base64
import hashlib
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings

from core.models import Client, File, Project, User
from core.storage_reconciliation import StorageReconciliationError, reconcile_ready_files

PASSWORD = "Synthetic-Reconcile-72!Leaf"


def file_record(payload=b"synthetic", **changes):
    values = {
        "object_key": "private/secret-client-object.mp4",
        "storage_version": "version-1",
        "size_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    values.update(changes)
    return SimpleNamespace(**values)


class StorageReconciliationUnitTests(SimpleTestCase):
    def test_exact_version_size_and_checksum_reconcile(self):
        payload = b"synthetic"
        client = SimpleNamespace(
            head_object=lambda **kwargs: {
                "ContentLength": len(payload),
                "ChecksumSHA256": base64.b64encode(hashlib.sha256(payload).digest()).decode(),
            }
        )
        report = reconcile_ready_files([file_record(payload)], client, "private-media")
        self.assertEqual(report["checked"], 1)

    def test_aggregate_failure_omits_private_identifiers(self):
        client = SimpleNamespace(
            head_object=lambda **kwargs: {"ContentLength": 999, "ChecksumSHA256": "wrong"}
        )
        with self.assertRaises(StorageReconciliationError) as raised:
            reconcile_ready_files([file_record()], client, "private-media")
        message = str(raised.exception)
        self.assertIn("size_mismatch=1", message)
        self.assertIn("checksum_mismatch=1", message)
        self.assertNotIn("secret-client-object", message)


class StorageReconciliationCommandTests(TestCase):
    @override_settings(S3_ENDPOINT_URL="https://storage.example.test", S3_BUCKET="private-media")
    def test_command_checks_ready_records_and_omits_identifiers(self):
        user = User.objects.create_user(
            "reconcile-client@example.test", PASSWORD, name="Reconcile Client"
        )
        project = Project.objects.create(client=Client.objects.create(user=user), title="Private")
        payload = b"synthetic"
        File.objects.create(
            project=project,
            uploader=user,
            filename="private-client-name.mp4",
            object_key="private/secret-client-object.mp4",
            storage_version="version-1",
            content_type="video/mp4",
            size_bytes=len(payload),
            sha256=hashlib.sha256(payload).hexdigest(),
            category="source",
            state="ready",
            expires_at="2030-01-01T00:00:00Z",
        )
        client = SimpleNamespace(
            head_object=lambda **kwargs: {
                "ContentLength": len(payload),
                "ChecksumSHA256": base64.b64encode(hashlib.sha256(payload).digest()).decode(),
            }
        )
        output = StringIO()
        with patch(
            "core.management.commands.reconcile_private_storage.storage_client",
            return_value=client,
        ):
            call_command("reconcile_private_storage", stdout=output)
        self.assertIn("passed for 1 ready file", output.getvalue())
        self.assertNotIn("private-client-name", output.getvalue())
        self.assertNotIn("secret-client-object", output.getvalue())

    @override_settings(S3_ENDPOINT_URL="", S3_BUCKET="")
    def test_command_rejects_missing_storage_configuration(self):
        with self.assertRaisesMessage(CommandError, "must be configured"):
            call_command("reconcile_private_storage")
