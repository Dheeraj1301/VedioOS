"""Opt-in Edge verification for revision-plan selection and deselection."""

import json
import os
import secrets
import subprocess
from unittest import skipUnless

from django.contrib.staticfiles.testing import StaticLiveServerTestCase

from core.models import Client, User
from operations.models import Admin


@skipUnless(os.getenv("RUN_REVISION_PLANS_BROWSER") == "1", "Requires Microsoft Edge")
class RevisionPlanBrowserTests(StaticLiveServerTestCase):
    def test_only_one_revision_plan_can_be_selected_and_selected_plan_can_be_deselected(self):
        password = secrets.token_urlsafe(24)
        user = User.objects.create_user(
            "revision-plan-browser@example.test", password, name="Revision Plan Browser"
        )
        Client.objects.create(user=user)
        admin = User.objects.create_user(
            "revision-plan-admin@example.test",
            password,
            name="Revision Plan Admin",
            role="admin",
        )
        Admin.objects.create(user=admin)
        result = subprocess.run(
            ["node", "tests/revision_plans_browser.mjs"],
            env={
                **os.environ,
                "REVISION_PLANS_BROWSER_FIXTURE": json.dumps(
                    {
                        "base": self.live_server_url,
                        "email": user.email,
                        "admin_email": admin.email,
                        "password": password,
                    }
                ),
            },
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, (result.stdout or "") + (result.stderr or ""))
        print(result.stdout)
