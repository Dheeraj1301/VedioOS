"""Opt-in Edge check for mobile client upload and message audience isolation."""

import json
import os
import secrets
import subprocess
from copy import deepcopy
from unittest import skipUnless

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings

from core.models import File, UploadPolicy
from core.storage import storage_client
from operations.models import EditorAssignment, EditorProficiency, Notification, ProjectMessage
from tests.assignment_fixtures import create_people, paid_project


@skipUnless(os.getenv("RUN_PHASE7_BROWSER") == "1", "Requires Edge and private local S3")
@override_settings(DEBUG=False)
class Phase7BrowserTests(StaticLiveServerTestCase):
    def test_mobile_original_upload_and_message_visibility(self):
        EditorProficiency.objects.get_or_create(level="beginner")
        UploadPolicy.objects.update_or_create(
            pk=1,
            defaults={"max_bytes": 8 * 1048576, "allowed_types": {".mp4": ["video/mp4"]}},
        )
        password = secrets.token_urlsafe(24)
        admin, client, editors = create_people(password=password)
        project = paid_project(client, title="Synthetic mobile project")
        EditorAssignment.objects.create(project=project, editor=editors[0], assigned_by=admin)
        for number in range(55):
            Notification.objects.create(
                recipient=client.user,
                project=project if number % 2 else None,
                event_key=f"phase7-browser-{number}",
                message=f"Synthetic update {number}",
            )
        fixture = {
            "base": self.live_server_url,
            "password": password,
            "admin": admin.email,
            "client": client.user.email,
            "editor": editors[0].user.email,
            "project": str(project.pk),
        }
        storage = storage_client()
        original_cors = storage.get_bucket_cors(Bucket=settings.S3_BUCKET)["CORSRules"]
        test_cors = deepcopy(original_cors)
        for rule in test_cors:
            rule["AllowedOrigins"] = list(dict.fromkeys([*rule["AllowedOrigins"], self.live_server_url]))
        storage.put_bucket_cors(Bucket=settings.S3_BUCKET, CORSConfiguration={"CORSRules": test_cors})
        try:
            result = subprocess.run(
                ["node", "tests/phase7_browser.mjs"],
                env={**os.environ, "PHASE7_BROWSER_FIXTURE": json.dumps(fixture)},
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=180,
            )
            self.assertEqual(result.returncode, 0, (result.stdout or "") + (result.stderr or ""))
            self.assertEqual(File.objects.filter(project=project, state="ready").count(), 2)
            self.assertTrue(
                File.objects.filter(
                    project=project,
                    state="ready",
                    category="reference",
                    filename="phase7-inspiration.mp4",
                ).exists()
            )
            self.assertEqual(ProjectMessage.objects.filter(project=project).count(), 2)
            print(result.stdout)
        finally:
            storage.put_bucket_cors(
                Bucket=settings.S3_BUCKET, CORSConfiguration={"CORSRules": original_cors}
            )
            for file in File.objects.filter(project=project):
                versions = storage.list_object_versions(Bucket=settings.S3_BUCKET, Prefix=file.object_key)
                for version in versions.get("Versions", []) + versions.get("DeleteMarkers", []):
                    storage.delete_object(
                        Bucket=settings.S3_BUCKET, Key=version["Key"], VersionId=version["VersionId"]
                    )
