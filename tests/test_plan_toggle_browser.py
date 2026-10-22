"""Opt-in real Edge verification for toggleable new-order plan cards."""

import json
import os
import secrets
import subprocess
from unittest import skipUnless

from django.contrib.staticfiles.testing import StaticLiveServerTestCase

from core.models import Client, Plan, UploadPolicy, User


@skipUnless(os.getenv("RUN_PLAN_TOGGLE_BROWSER") == "1", "Requires Microsoft Edge")
class PlanToggleBrowserTests(StaticLiveServerTestCase):
    def test_plan_and_custom_toggle_without_losing_form_state(self):
        password = secrets.token_urlsafe(24)
        user = User.objects.create_user(
            "plan-toggle-browser@example.test", password, name="Plan Toggle Browser"
        )
        Client.objects.create(user=user)
        UploadPolicy.objects.create(max_bytes=1024 * 1024, allowed_types={".mp4": ["video/mp4"]})
        plans = [
            Plan.objects.create(
                slot=slot,
                name=f"Toggle plan {slot}",
                price_minor=slot * 10000,
                currency="INR",
                features=["Cuts"],
                revision_limit=1,
                delivery_hours=24,
                duration_limit_seconds=60,
                priority=slot,
                active=True,
            )
            for slot in range(1, 4)
        ]
        result = subprocess.run(
            ["node", "tests/plan_toggle_browser.mjs"],
            env={
                **os.environ,
                "PLAN_TOGGLE_BROWSER_FIXTURE": json.dumps(
                    {
                        "base": self.live_server_url,
                        "email": user.email,
                        "password": password,
                        "plan_ids": [str(plan.id) for plan in plans],
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
