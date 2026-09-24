import base64
import hashlib
from io import StringIO
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from core.storage_preflight import check_private_storage


class FakeStorage:
    def __init__(self, *, versioning="Enabled", anonymous=False):
        self.versioning = versioning
        self.anonymous = anonymous
        self.key = None
        self.payload = None
        self.versions = []

    def get_bucket_versioning(self, **kwargs):
        return {"Status": self.versioning}

    def put_object(self, *, Key, Body, **kwargs):
        self.key = Key
        self.payload = Body
        self.versions = [{"Key": Key, "VersionId": "synthetic-version"}]
        return {"VersionId": "synthetic-version"}

    def head_object(self, **kwargs):
        return {
            "ContentLength": len(self.payload),
            "ChecksumSHA256": base64.b64encode(hashlib.sha256(self.payload).digest()).decode(),
        }

    def generate_presigned_url(self, *args, **kwargs):
        return "https://signed.example.test/probe"

    def list_object_versions(self, **kwargs):
        return {"Versions": list(self.versions)}

    def delete_object(self, **kwargs):
        self.versions = []


class StoragePreflightTests(SimpleTestCase):
    def test_round_trip_is_private_versioned_and_cleaned(self):
        storage = FakeStorage()

        def response(url, **kwargs):
            if url.startswith("https://signed"):
                return Mock(status_code=200, content=storage.payload)
            return Mock(status_code=403, content=b"")

        with patch("core.storage_preflight.requests.get", side_effect=response):
            result = check_private_storage(
                storage, "https://storage.example.test", "private-media", payload=b"synthetic"
            )
        self.assertTrue(result["versioned"])
        self.assertEqual(result["anonymous_status"], 403)
        self.assertEqual(storage.versions, [])

    def test_failure_still_removes_the_probe(self):
        storage = FakeStorage()
        with (
            patch(
                "core.storage_preflight.requests.get",
                return_value=Mock(status_code=200, content=b"changed"),
            ),
            self.assertRaisesMessage(Exception, "preserve the uploaded bytes"),
        ):
            check_private_storage(
                storage, "https://storage.example.test", "private-media", payload=b"synthetic"
            )
        self.assertEqual(storage.versions, [])

    @override_settings(
        S3_ENDPOINT_URL="https://storage.example.test",
        S3_BUCKET="private-media",
        DOWNLOAD_TTL_SECONDS=60,
    )
    def test_command_reports_success_without_urls_or_credentials(self):
        storage = FakeStorage()

        def response(url, **kwargs):
            content = storage.payload if url.startswith("https://signed") else b""
            status = 200 if url.startswith("https://signed") else 403
            return Mock(status_code=status, content=content)

        output = StringIO()
        with (
            patch(
                "core.management.commands.check_private_storage.storage_client",
                return_value=storage,
            ),
            patch("core.storage_preflight.requests.get", side_effect=response),
        ):
            call_command("check_private_storage", stdout=output)
        self.assertIn("anonymous access was denied", output.getvalue())
        self.assertNotIn("signed.example.test", output.getvalue())

    @override_settings(S3_ENDPOINT_URL="", S3_BUCKET="")
    def test_command_rejects_missing_configuration(self):
        with self.assertRaisesMessage(CommandError, "must be configured"):
            call_command("check_private_storage")
