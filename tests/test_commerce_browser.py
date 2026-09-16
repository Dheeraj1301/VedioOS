"""Opt-in real Edge browser flow against Django's isolated, temporary test database."""

import json
import os
import secrets
import subprocess
from unittest import skipUnless

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings

from core.models import Client, Order, Payment, Project, User


@skipUnless(os.getenv("RUN_COMMERCE_BROWSER") == "1", "Opt-in browser test")
@override_settings(DEBUG=True, PAYMENT_MODE="sandbox")
class CommerceBrowserTests(StaticLiveServerTestCase):
    def test_admin_catalog_client_quote_signed_payment_receipt(self):
        password = secrets.token_urlsafe(24)
        secret = secrets.token_urlsafe(40)
        User.objects.create_user("browser-admin@example.test", password, name="Test Admin", role="admin")
        buyer = User.objects.create_user("browser-buyer@example.test", password, name="Test Buyer")
        project = Project.objects.create(
            client=Client.objects.create(user=buyer), title="Synthetic phase 3 edit"
        )
        Order.objects.create(project=project)
        env = {
            **os.environ,
            "COMMERCE_BROWSER_FIXTURE": json.dumps(
                {
                    "base": self.live_server_url,
                    "password": password,
                    "secret": secret,
                    "project": str(project.id),
                }
            ),
        }
        with override_settings(SANDBOX_PAYMENT_SECRET=secret):
            result = subprocess.run(
                ["node", "tests/commerce_browser.mjs"], env=env, capture_output=True, text=True, timeout=150
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(Payment.objects.get().amount_minor, 11500)
        project.refresh_from_db()
        self.assertEqual(project.status, "payment_completed")
        self.assertEqual(Project.objects.count(), 1)
        self.assertIsNone(project.expected_delivery_at)
        print(result.stdout)
