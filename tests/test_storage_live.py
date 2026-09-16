"""Opt-in integration tests against real S3 storage. No transport mocks."""

import base64
import hashlib
import json
import os
import time
import uuid
from unittest import skipUnless

import requests
from django.conf import settings
from django.test import Client as Browser
from django.test import TestCase, override_settings

from core.models import Client, File, Project, UploadPolicy, User
from core.storage import storage_client


@skipUnless(
    os.getenv("RUN_STORAGE_TESTS") == "1", "Set RUN_STORAGE_TESTS=1 with local private storage running."
)
class LiveStorageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            f"{uuid.uuid4()}@example.test", "Storage-Test-Pass-83!", name="Storage Test"
        )
        self.project = Project.objects.create(
            client=Client.objects.create(user=self.user), title="Storage integration"
        )
        self.browser = Browser()
        self.browser.force_login(self.user)
        UploadPolicy.objects.create(max_bytes=8 * 1024 * 1024, allowed_types={".mp4": ["video/mp4"]})
        # Synthetic bytes only, including binary data. This does not claim codec validation.
        self.payload = b"\x00\x00\x00\x18ftypmp42" + bytes(range(256)) * 20000

    def tearDown(self):
        client = storage_client()
        for file in File.objects.filter(project=self.project):
            result = client.list_object_versions(Bucket=settings.S3_BUCKET, Prefix=file.object_key)
            for version in result.get("Versions", []) + result.get("DeleteMarkers", []):
                client.delete_object(
                    Bucket=settings.S3_BUCKET, Key=version["Key"], VersionId=version["VersionId"]
                )

    def reserve(self, payload=None):
        payload = self.payload if payload is None else payload
        response = self.browser.post(
            f"/api/projects/{self.project.id}/uploads/",
            data=json.dumps(
                {
                    "filename": "synthetic.mp4",
                    "size_bytes": len(payload),
                    "content_type": "video/mp4",
                    "category": "source",
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def upload(self, reservation, payload=None):
        payload = self.payload if payload is None else payload
        permission = reservation["upload"]
        response = requests.put(permission["url"], data=payload, headers=permission["headers"], timeout=60)
        self.assertIn(response.status_code, [200, 201], response.text[:600])
        response = self.browser.post(f"/api/files/{reservation['file_id']}/complete/")
        self.assertEqual(response.status_code, 200, response.content)
        return File.objects.get(pk=reservation["file_id"])

    def test_original_roundtrip_private_access_version_and_overwrite(self):
        reservation = self.reserve()
        file = self.upload(reservation)
        self.assertTrue(file.storage_version)
        response = self.browser.post(f"/api/files/{file.id}/download/")
        self.assertEqual(response.status_code, 200)
        download = requests.get(response.json()["url"], timeout=30)
        self.assertEqual(
            download.status_code, 200, download.text[:100] if download.status_code != 200 else ""
        )
        self.assertEqual(hashlib.sha256(download.content).hexdigest(), file.sha256)
        self.assertEqual(download.content, self.payload)
        public_url = f"{settings.S3_ENDPOINT_URL}/{settings.S3_BUCKET}/{file.object_key}"
        self.assertEqual(requests.get(public_url, timeout=10).status_code, 403)
        self.assertEqual(
            requests.get(f"{settings.S3_ENDPOINT_URL}/{settings.S3_BUCKET}", timeout=10).status_code, 403
        )
        replay = requests.put(
            reservation["upload"]["url"],
            data=self.payload,
            headers=reservation["upload"]["headers"],
            timeout=30,
        )
        self.assertEqual(replay.status_code, 412, replay.text[:200])
        second = self.reserve()
        second_file = self.upload(second)
        self.assertNotEqual(file.object_key, second_file.object_key)
        self.assertEqual(requests.get(response.json()["url"], timeout=30).content, self.payload)
        self.assertEqual(Browser().post(f"/api/files/{file.id}/download/").status_code, 401)
        # CORS preflight for the actual browser upload headers.
        cors = requests.options(
            reservation["upload"]["url"],
            headers={
                "Origin": "http://127.0.0.1:8000",
                "Access-Control-Request-Method": "PUT",
                "Access-Control-Request-Headers": "content-type,if-none-match,x-amz-checksum-sha256",
            },
            timeout=10,
        )
        self.assertIn(cors.status_code, [200, 204])
        self.assertIn(cors.headers.get("Access-Control-Allow-Origin"), ["http://127.0.0.1:8000"])

    def test_checksum_mismatch_is_rejected_by_storage(self):
        reservation = self.reserve()
        bad_bytes = b"x" * len(self.payload)
        response = requests.put(
            reservation["upload"]["url"], data=bad_bytes, headers=reservation["upload"]["headers"], timeout=30
        )
        self.assertIn(response.status_code, [400, 403], response.text[:200])
        self.assertEqual(self.browser.post(f"/api/files/{reservation['file_id']}/complete/").status_code, 409)

    def test_expired_download_permission(self):
        file = self.upload(self.reserve())
        with override_settings(DOWNLOAD_TTL_SECONDS=1):
            link = self.browser.post(f"/api/files/{file.id}/download/").json()["url"]
        self.assertEqual(requests.get(link, timeout=10).status_code, 200)
        time.sleep(2)
        self.assertEqual(requests.get(link, timeout=10).status_code, 403)

    def test_incomplete_upload_never_becomes_ready(self):
        reservation = self.reserve()
        self.assertEqual(self.browser.post(f"/api/files/{reservation['file_id']}/complete/").status_code, 409)
        self.assertEqual(File.objects.get(pk=reservation["file_id"]).state, "pending")

    def test_signed_size_cannot_be_changed(self):
        reservation = self.reserve()
        smaller = self.payload[:12]
        headers = dict(reservation["upload"]["headers"])
        headers["x-amz-checksum-sha256"] = base64.b64encode(hashlib.sha256(smaller).digest()).decode()
        response = requests.put(reservation["upload"]["url"], data=smaller, headers=headers, timeout=30)
        self.assertEqual(response.status_code, 403, response.text[:200])
