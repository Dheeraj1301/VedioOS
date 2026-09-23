from django.test import Client as Browser
from django.test import TestCase

from core.models import Client, Order, Project, User
from operations.analytics import operational_analytics
from operations.models import (
    Admin,
    Editor,
    EditorAssignment,
    EditorAvailability,
    EditorCoins,
    Notification,
    RedemptionRequest,
)

PASSWORD = "Synthetic-Analytics-72!Leaf"


class OperationalAnalyticsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            "analytics-admin@example.test", PASSWORD, name="Admin", role="admin"
        )
        Admin.objects.create(user=cls.admin)
        cls.client_user = User.objects.create_user(
            "analytics-client@example.test", PASSWORD, name="Client"
        )
        client = Client.objects.create(user=cls.client_user)
        cls.open_project = Project.objects.create(
            client=client, title="Open project", status=Project.Status.EDITING
        )
        Order.objects.create(
            project=cls.open_project,
            payment_status="confirmed",
            total_minor=12000,
            currency="INR",
        )
        completed = Project.objects.create(
            client=client, title="Completed project", status=Project.Status.COMPLETED
        )
        Order.objects.create(project=completed, payment_status="refunded")
        editor_user = User.objects.create_user(
            "analytics-editor@example.test", PASSWORD, name="Editor", role="editor"
        )
        editor = Editor.objects.create(
            user=editor_user,
            phone="1234567890",
            experience="Synthetic experience",
            tools="Synthetic tools",
            portfolio="https://example.test/portfolio",
            previous_work="Synthetic work",
            expertise="Editing",
            approved=True,
            approved_by=cls.admin,
            proficiency_id="beginner",
            workload_capacity=2,
        )
        EditorAvailability.objects.create(editor=editor, status="available")
        EditorAssignment.objects.create(
            project=cls.open_project, editor=editor, assigned_by=cls.admin
        )
        wallet = EditorCoins.objects.create(editor=editor)
        RedemptionRequest.objects.create(wallet=wallet, amount=10)
        Notification.objects.create(
            recipient=cls.client_user,
            project=cls.open_project,
            event_key="analytics-notice",
            message="Synthetic update.",
        )

    def test_counts_reconcile_to_source_records(self):
        snapshot = operational_analytics()
        self.assertEqual(snapshot["headline"]["clients"], 1)
        self.assertEqual(snapshot["headline"]["orders"], 2)
        self.assertEqual(snapshot["headline"]["paid_orders"], 1)
        self.assertEqual(snapshot["headline"]["open_projects"], 1)
        self.assertEqual(snapshot["headline"]["completed_projects"], 1)
        self.assertEqual(snapshot["headline"]["open_assignments"], 1)
        self.assertEqual(snapshot["headline"]["pending_payouts"], 1)
        self.assertEqual(snapshot["editors"]["available"], 1)
        self.assertEqual(
            next(row["count"] for row in snapshot["deliveries"] if row["key"] == "held"),
            1,
        )

    def test_admin_page_is_protected_and_omits_undefined_financial_metrics(self):
        self.assertEqual(Browser().get("/admin/analytics/").status_code, 302)
        client_browser = Browser()
        client_browser.force_login(self.client_user)
        self.assertEqual(client_browser.get("/admin/analytics/").status_code, 403)
        admin_browser = Browser()
        admin_browser.force_login(self.admin)
        response = admin_browser.get("/admin/analytics/")
        self.assertContains(response, "Operational snapshot")
        self.assertContains(response, "Metrics awaiting policy")
        self.assertNotContains(response, "Total revenue")
