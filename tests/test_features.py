from django.test import Client as Browser
from django.test import TestCase, override_settings

from core.models import Client, CommercePolicy, UploadPolicy, User
from operations.features import feature_controls
from operations.models import Admin, AssignmentPolicy, EarningPolicy

PASSWORD = "Synthetic-Features-72!Leaf"


class FeatureControlTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            "features-admin@example.test", PASSWORD, name="Admin", role="admin"
        )
        Admin.objects.create(user=cls.admin)
        cls.client_user = User.objects.create_user(
            "features-client@example.test", PASSWORD, name="Client"
        )
        Client.objects.create(user=cls.client_user)

    def test_feature_inventory_is_admin_only(self):
        self.assertEqual(Browser().get("/admin/features/").status_code, 302)
        client = Browser()
        client.force_login(self.client_user)
        self.assertEqual(client.get("/admin/features/").status_code, 403)
        admin = Browser()
        admin.force_login(self.admin)
        response = admin.get("/admin/features/")
        self.assertContains(response, "Feature controls")
        self.assertContains(response, "Monthly package sales")
        self.assertContains(response, "Locked pending D13")
        self.assertContains(response, "Owner decisions required")
        self.assertContains(response, "Open decision checklist")
        for number in range(2, 17):
            self.assertContains(response, f"D{number:02d} ·")

    @override_settings(
        DEBUG=True,
        PAYMENT_MODE="sandbox",
        PAYOUT_MODE="sandbox",
        NOTIFICATION_EMAIL_ENABLED=True,
    )
    def test_inventory_reflects_real_policy_and_environment_controls(self):
        CommercePolicy.objects.update_or_create(
            pk=1,
            defaults={
                "currency": "INR",
                "terms": "Synthetic terms",
                "delivery_terms": "Synthetic delivery",
                "refund_terms": "Synthetic refunds",
                "tax_terms": "Synthetic taxes",
                "quotes_enabled": True,
                "review_rule": "latest_request_v1",
            },
        )
        AssignmentPolicy.objects.update_or_create(
            pk=1,
            defaults={
                "manual_enabled": True,
                "automatic_enabled": True,
                "matching": "exact",
                "capacity_scope": "open_assignments",
                "manual_pointer": "preserve",
                "busy_strategy": "skip",
                "roster_order": "joined",
                "queue_order": "paid_at",
            },
        )
        EarningPolicy.objects.update_or_create(
            pk=1,
            defaults={
                "enabled": True,
                "rule": "fixed_whole_v1",
                "plan_1_coins": 1,
                "plan_2_coins": 2,
                "plan_3_coins": 3,
                "custom_coins": 4,
                "release_mode": "manual",
                "redemptions_enabled": True,
                "redemption_minimum": 1,
            },
        )
        UploadPolicy.objects.update_or_create(
            pk=1, defaults={"enabled": True, "max_bytes": 1024, "allowed_types": {}}
        )
        states = {item["name"]: item["state"] for item in feature_controls()["features"]}
        for name in [
            "Client quotes",
            "Review and acceptance",
            "Private uploads",
            "Manual assignment",
            "Automatic assignment",
            "Editor earnings",
            "Coin redemptions",
            "External notification email",
        ]:
            self.assertEqual(states[name], "Enabled")
        self.assertEqual(states["Payment gateway"], "Development sandbox")
        self.assertEqual(states["Payout processing"], "Development sandbox")
        self.assertEqual(
            [item["id"] for item in feature_controls()["launch_decisions"]],
            [f"D{number:02d}" for number in range(2, 17)],
        )
