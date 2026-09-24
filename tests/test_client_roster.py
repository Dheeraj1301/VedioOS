from django.test import Client as Browser
from django.test import TestCase
from django.utils import timezone

from core.models import Client, Order, Project, User
from operations.clients import client_page
from operations.models import Admin, SupportRequest

PASSWORD = "Synthetic-Clients-72!Leaf"


class ClientRosterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            "client-admin@example.test", PASSWORD, name="Admin", role="admin"
        )
        Admin.objects.create(user=cls.admin)
        cls.active_user = User.objects.create_user(
            "active-client@example.test", PASSWORD, name="Active Client"
        )
        cls.active = Client.objects.create(user=cls.active_user)
        open_project = Project.objects.create(
            client=cls.active, title="Open work", status=Project.Status.EDITING
        )
        Order.objects.create(project=open_project, payment_status="confirmed")
        completed = Project.objects.create(
            client=cls.active, title="Completed work", status=Project.Status.COMPLETED
        )
        Order.objects.create(project=completed, payment_status="refunded")
        SupportRequest.objects.create(
            client=cls.active,
            subject="Open support",
            category=SupportRequest.Category.PROJECT,
            request_key="b1dadba8-46b5-4865-9025-4a7baef7ef14",
        )
        awaiting_user = User.objects.create_user(
            "awaiting-client@example.test", PASSWORD, name="Awaiting Client", is_active=False
        )
        cls.awaiting = Client.objects.create(user=awaiting_user)
        inactive_user = User.objects.create_user(
            "inactive-client@example.test",
            PASSWORD,
            name="Inactive Client",
            is_active=False,
            email_verified_at=timezone.now(),
        )
        cls.inactive = Client.objects.create(user=inactive_user)

    def test_annotations_reconcile_and_filters_are_server_side(self):
        clients, cursor, state, search = client_page(state="active", search="active-client")
        self.assertIsNone(cursor)
        self.assertEqual(state, "active")
        self.assertEqual(search, "active-client")
        self.assertEqual(len(clients), 1)
        client = clients[0]
        self.assertEqual(client.project_count, 2)
        self.assertEqual(client.open_project_count, 1)
        self.assertEqual(client.completed_project_count, 1)
        self.assertEqual(client.confirmed_order_count, 1)
        self.assertEqual(client.open_support_count, 1)
        self.assertEqual(client_page(state="awaiting_verification")[0][0].id, self.awaiting.id)
        self.assertEqual(client_page(state="inactive")[0][0].id, self.inactive.id)

    def test_cursor_is_stable_and_invalid_cursor_is_rejected(self):
        first, cursor, _state, _search = client_page(size=2)
        self.assertEqual(len(first), 2)
        self.assertIsNotNone(cursor)
        older, older_cursor, _state, _search = client_page(before=cursor, size=2)
        self.assertEqual(len(older), 1)
        self.assertIsNone(older_cursor)
        self.assertTrue(set(row.id for row in first).isdisjoint(row.id for row in older))
        admin = Browser()
        admin.force_login(self.admin)
        self.assertEqual(admin.get("/admin/clients/", {"before": "invalid"}).status_code, 404)

    def test_admin_page_is_protected_and_renders_operational_state(self):
        self.assertEqual(Browser().get("/admin/clients/").status_code, 302)
        client_browser = Browser()
        client_browser.force_login(self.active_user)
        self.assertEqual(client_browser.get("/admin/clients/").status_code, 403)
        admin = Browser()
        admin.force_login(self.admin)
        response = admin.get("/admin/clients/", {"q": "Active", "state": "active"})
        self.assertContains(response, "Client operations")
        self.assertContains(response, "Active Client")
        self.assertContains(response, "Confirmed orders")
        self.assertNotContains(response, "Awaiting Client")
