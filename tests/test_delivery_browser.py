import json
import os
import secrets
import subprocess
from unittest import skipUnless

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings

from core.models import DeliveryAcceptance, File, UploadPolicy
from core.storage import storage_client
from operations.models import AssignmentPolicy, EditorProficiency
from tests.assignment_fixtures import create_people
from tests.test_delivery import delivery_fixture


@skipUnless(os.getenv("RUN_DELIVERY_BROWSER") == "1", "Requires Edge and private local S3")
@override_settings(DEBUG=True)
class DeliveryBrowserTests(StaticLiveServerTestCase):
    def test_review_revision_acceptance_and_original_bytes(self):
        for level in ["beginner", "intermediate", "advanced"]:
            EditorProficiency.objects.get_or_create(level=level)
        AssignmentPolicy.objects.get_or_create(pk=1)
        UploadPolicy.objects.update_or_create(
            pk=1, defaults={"max_bytes": 1048576, "allowed_types": {".mp4": ["video/mp4"]}}
        )
        password = secrets.token_urlsafe(24)
        _, buyer, editors = create_people(password=password)
        projects = [delivery_fixture(buyer, editors[0]), delivery_fixture(buyer, editors[1])]
        fixture = {
            "base": self.live_server_url,
            "password": password,
            "buyer": buyer.user.email,
            "editors": [e.user.email for e in editors],
            "projects": [str(p.pk) for p in projects],
        }
        try:
            result = subprocess.run(
                ["node", "tests/delivery_browser.mjs"],
                env={**os.environ, "DELIVERY_BROWSER_FIXTURE": json.dumps(fixture)},
                capture_output=True,
                text=True,
                timeout=180,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(DeliveryAcceptance.objects.count(), 2)
            self.assertEqual(projects[0].versions.count(), 2)
            self.assertEqual(projects[1].versions.count(), 1)
            print(result.stdout)
        finally:
            storage = storage_client()
            for file in File.objects.filter(project__in=projects):
                versions = storage.list_object_versions(Bucket=settings.S3_BUCKET, Prefix=file.object_key)
                for version in versions.get("Versions", []) + versions.get("DeleteMarkers", []):
                    storage.delete_object(
                        Bucket=settings.S3_BUCKET, Key=version["Key"], VersionId=version["VersionId"]
                    )
