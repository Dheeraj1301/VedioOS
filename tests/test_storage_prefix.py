from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings

from core.landing_views import _upload_video
from core.storage import storage_key
from core.storage_inventory import inventory_private_storage


class FakeVersions:
    def __init__(self, keys):
        self.keys, self.requests = keys, []

    def list_object_versions(self, **request):
        self.requests.append(request)
        return {"Versions": [{"Key": key, "VersionId": "v1"} for key in self.keys], "IsTruncated": False}


@override_settings(S3_KEY_PREFIX="edits/")
class StoragePrefixTests(SimpleTestCase):
    def test_new_object_keys_live_under_the_prefix(self):
        self.assertEqual(storage_key("projects/p/f"), "edits/projects/p/f")
        with patch("core.landing_views.storage_client") as client:
            client.return_value.put_object.return_value = {"VersionId": "v1"}
            key, _version, _digest = _upload_video(SimpleUploadedFile("hero.mp4", b"\x00" * 64, "video/mp4"))
        self.assertTrue(key.startswith("edits/landing/hero/"))

    def test_inventory_only_lists_the_prefix_and_skips_its_probe_files(self):
        client = FakeVersions(["edits/__vedioos_checks__/a.bin", "edits/projects/p/f"])
        report = inventory_private_storage([], client, "bucket")
        self.assertEqual(client.requests[0]["Prefix"], "edits/")
        self.assertEqual(report["probe_artifacts"], 1)

    @override_settings(S3_KEY_PREFIX="")
    def test_no_prefix_keeps_existing_paths(self):
        self.assertEqual(storage_key("projects/p/f"), "projects/p/f")
