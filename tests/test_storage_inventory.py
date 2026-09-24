import json
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from core.storage_inventory import inventory_private_storage


def file_record(key, version, state="ready"):
    return SimpleNamespace(object_key=key, storage_version=version, state=state)


class PaginatedStorage:
    def list_object_versions(self, **request):
        if "KeyMarker" not in request:
            return {
                "Versions": [{"Key": "private/referenced", "VersionId": "v1"}],
                "IsTruncated": True,
                "NextKeyMarker": "private/referenced",
                "NextVersionIdMarker": "v1",
            }
        return {
            "Versions": [{"Key": "private/unreferenced", "VersionId": "v2"}],
            "DeleteMarkers": [{"Key": "private/deleted", "VersionId": "d1"}],
            "IsTruncated": False,
        }


class StorageInventoryTests(SimpleTestCase):
    def test_paginated_inventory_separates_critical_findings_from_warnings(self):
        report = inventory_private_storage(
            [file_record("private/referenced", "v1")], PaginatedStorage(), "private-media"
        )
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["database_references"], 1)
        self.assertEqual(report["bucket_versions"], 2)
        self.assertEqual(report["unreferenced_versions"], 1)
        self.assertEqual(report["delete_markers"], 1)
        self.assertEqual(report["warning_count"], 2)

    def test_missing_reference_and_probe_artifact_fail_without_identifiers(self):
        storage = SimpleNamespace(
            list_object_versions=lambda **kwargs: {
                "Versions": [
                    {"Key": "__vedioos_checks__/private-probe.bin", "VersionId": "probe-v1"}
                ]
            }
        )
        report = inventory_private_storage(
            [file_record("private/client-secret.mp4", "missing-v1")], storage, "private-media"
        )
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["missing_referenced_versions"], 1)
        self.assertEqual(report["probe_artifacts"], 1)
        self.assertNotIn("client-secret", json.dumps(report))
        self.assertNotIn("private-probe", json.dumps(report))

    @override_settings(S3_ENDPOINT_URL="https://storage.example.test", S3_BUCKET="private-media")
    def test_command_outputs_only_aggregate_counts(self):
        report = {
            "status": "pass",
            "code": "inventory_consistent",
            "database_references": 1,
            "bucket_objects": 2,
            "bucket_versions": 2,
            "ready_without_version": 0,
            "missing_referenced_versions": 0,
            "probe_artifacts": 0,
            "unreferenced_versions": 1,
            "delete_markers": 0,
            "pending_records": 3,
            "warning_count": 1,
        }
        output = StringIO()
        with patch(
            "core.management.commands.inventory_private_storage.inventory_private_storage",
            return_value=report,
        ):
            call_command("inventory_private_storage", stdout=output)
        self.assertIn("unreferenced versions=1", output.getvalue())
        self.assertNotIn("object_key", output.getvalue())

    @override_settings(S3_ENDPOINT_URL="https://storage.example.test", S3_BUCKET="private-media")
    def test_command_fails_on_critical_inventory_findings(self):
        report = {
            "status": "fail",
            "code": "storage_inventory_failed",
            "database_references": 1,
            "bucket_objects": 0,
            "bucket_versions": 0,
            "ready_without_version": 0,
            "missing_referenced_versions": 1,
            "probe_artifacts": 0,
            "unreferenced_versions": 0,
            "delete_markers": 0,
            "pending_records": 0,
            "warning_count": 0,
        }
        with patch(
            "core.management.commands.inventory_private_storage.inventory_private_storage",
            return_value=report,
        ):
            with self.assertRaisesMessage(CommandError, "critical findings"):
                call_command("inventory_private_storage", stdout=StringIO())
