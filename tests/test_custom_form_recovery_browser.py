"""Opt-in Edge check for custom-form validation, upload recovery, limits and removal."""

import json
import os
import secrets
import subprocess
from copy import deepcopy
from unittest import skipUnless

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings

from core.models import Client, File, UploadPolicy, User
from core.storage import storage_client


@skipUnless(os.getenv("RUN_CUSTOM_FORM_BROWSER") == "1", "Requires Edge and private local S3")
@override_settings(DEBUG=False)
class CustomFormRecoveryBrowserTests(StaticLiveServerTestCase):
    def test_validation_interruption_retry_limit_and_removal(self):
        password = secrets.token_urlsafe(24)
        user = User.objects.create_user(
            "custom-form-browser@example.test", password, name="Custom Form Browser"
        )
        Client.objects.create(user=user)
        UploadPolicy.objects.update_or_create(
            pk=1,
            defaults={"max_bytes": 8 * 1048576, "allowed_types": {".jpg": ["image/jpeg"]}},
        )
        storage = storage_client()
        original_cors = storage.get_bucket_cors(Bucket=settings.S3_BUCKET)["CORSRules"]
        test_cors = deepcopy(original_cors)
        for rule in test_cors:
            rule["AllowedOrigins"] = list(
                dict.fromkeys([*rule["AllowedOrigins"], self.live_server_url])
            )
        storage.put_bucket_cors(
            Bucket=settings.S3_BUCKET, CORSConfiguration={"CORSRules": test_cors}
        )
        try:
            result = subprocess.run(
                ["node", "tests/custom_form_recovery_browser.mjs"],
                env={
                    **os.environ,
                    "CUSTOM_FORM_BROWSER_FIXTURE": json.dumps(
                        {
                            "base": self.live_server_url,
                            "email": user.email,
                            "password": password,
                        }
                    ),
                },
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=180,
            )
            self.assertEqual(result.returncode, 0, (result.stdout or "") + (result.stderr or ""))
            self.assertEqual(File.objects.filter(state="ready", category="reference").count(), 2)
            self.assertEqual(File.objects.filter(state="removed", category="reference").count(), 2)
            print(result.stdout)
        finally:
            storage.put_bucket_cors(
                Bucket=settings.S3_BUCKET, CORSConfiguration={"CORSRules": original_cors}
            )
            for file in File.objects.all():
                versions = storage.list_object_versions(
                    Bucket=settings.S3_BUCKET, Prefix=file.object_key
                )
                for version in versions.get("Versions", []) + versions.get("DeleteMarkers", []):
                    storage.delete_object(
                        Bucket=settings.S3_BUCKET,
                        Key=version["Key"],
                        VersionId=version["VersionId"],
                    )
