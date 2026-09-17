import json
import os
import secrets
import subprocess
from unittest import skipUnless

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings

from core.delivery import transition
from operations.models import AssignmentPolicy, CoinTransaction, EarningPolicy, EditorProficiency
from tests.assignment_fixtures import create_people
from tests.test_delivery import delivery_fixture, ready_output
from tests.test_earnings import RULE


@skipUnless(os.getenv("RUN_EARNING_BROWSER") == "1", "Opt-in Edge browser test")
@override_settings(DEBUG=True, PAYOUT_MODE="sandbox")
class EarningBrowserTests(StaticLiveServerTestCase):
    def test_wallet_release_and_sandbox_redemption(self):
        for level in ["beginner", "intermediate", "advanced"]:
            EditorProficiency.objects.get_or_create(level=level)
        AssignmentPolicy.objects.get_or_create(pk=1)
        EarningPolicy.objects.update_or_create(pk=1, defaults={
            "enabled": True, "rule": "fixed_whole_v1", "plan_1_coins": 120,
            "plan_2_coins": 230, "plan_3_coins": 340, "custom_coins": 150,
            "release_mode": "manual", "redemptions_enabled": True, "redemption_minimum": 20,
        })
        password = secrets.token_urlsafe(24)
        admin, buyer, editors = create_people(password=password)
        project = delivery_fixture(buyer, editors[0])
        project.order.terms_snapshot = {"review_rule": "latest_request_v1", "revision_limit": 1, "earning_rule": RULE}
        project.order.save()
        file = ready_output(project, editors[0].user)
        transition(editors[0].user, project.pk, "start")
        transition(editors[0].user, project.pk, "submit", file_id=file.pk)
        transition(buyer.user, project.pk, "accept", version_id=project.versions.get().pk)
        fixture = {"base": self.live_server_url, "password": password,
                   "admin": admin.email, "editor": editors[0].user.email}
        result = subprocess.run(["node", "tests/earning_browser.mjs"],
                                env={**os.environ, "EARNING_BROWSER_FIXTURE": json.dumps(fixture)},
                                capture_output=True, text=True, timeout=150)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(CoinTransaction.objects.filter(kind="credit").count(), 1)
        self.assertEqual(CoinTransaction.objects.filter(kind="release").count(), 1)
        self.assertEqual(CoinTransaction.objects.filter(kind="redeem").count(), 1)
        print(result.stdout)
