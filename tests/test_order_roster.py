from django.test import Client as Browser
from django.test import TestCase

from core.models import Client, Order, Payment, Project, User
from operations.models import Admin
from operations.orders import order_page

PASSWORD = "Synthetic-Orders-72!Leaf"


class OrderRosterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            "order-admin@example.test", PASSWORD, name="Admin", role="admin"
        )
        Admin.objects.create(user=cls.admin)
        cls.client_user = User.objects.create_user(
            "order-client@example.test", PASSWORD, name="Order Client"
        )
        profile = Client.objects.create(user=cls.client_user)
        paid_project = Project.objects.create(
            client=profile, title="Paid editing order", status=Project.Status.EDITING
        )
        cls.paid = Order.objects.create(
            project=paid_project,
            payment_status="confirmed",
            total_minor=12000,
            currency="INR",
        )
        Payment.objects.create(
            order=cls.paid,
            provider="sandbox",
            provider_reference="order-roster-confirmed",
            amount_minor=12000,
            currency="INR",
            status="confirmed",
        )
        for number, status in enumerate(("pending", "failed", "refunded"), start=1):
            project = Project.objects.create(
                client=profile,
                title=f"Order state {number}",
                status=Project.Status.PENDING,
            )
            Order.objects.create(project=project, payment_status=status)

    def test_filters_and_annotations_reconcile(self):
        orders, cursor, payment, workflow, search = order_page(
            payment="paid", workflow=Project.Status.EDITING, search="Order Client"
        )
        self.assertIsNone(cursor)
        self.assertEqual(payment, "confirmed")
        self.assertEqual(workflow, Project.Status.EDITING)
        self.assertEqual(search, "Order Client")
        self.assertEqual([order.id for order in orders], [self.paid.id])
        self.assertEqual(orders[0].payment_attempt_count, 1)
        self.assertEqual(len(order_page(payment="unpaid")[0]), 3)

    def test_cursor_is_stable_and_invalid_cursor_is_rejected(self):
        first, cursor, _payment, _workflow, _search = order_page(size=2)
        self.assertEqual(len(first), 2)
        self.assertIsNotNone(cursor)
        older, older_cursor, _payment, _workflow, _search = order_page(before=cursor, size=2)
        self.assertEqual(len(older), 2)
        self.assertIsNone(older_cursor)
        self.assertTrue(set(row.id for row in first).isdisjoint(row.id for row in older))
        admin = Browser()
        admin.force_login(self.admin)
        self.assertEqual(admin.get("/admin/orders/", {"before": "invalid"}).status_code, 404)

    def test_admin_page_is_role_protected_and_renders_filters(self):
        self.assertEqual(Browser().get("/admin/orders/").status_code, 302)
        client = Browser()
        client.force_login(self.client_user)
        self.assertEqual(client.get("/admin/orders/").status_code, 403)
        admin = Browser()
        admin.force_login(self.admin)
        response = admin.get(
            "/admin/orders/",
            {"payment": "confirmed", "workflow": Project.Status.EDITING, "q": "Paid editing"},
        )
        self.assertContains(response, "Order operations")
        self.assertContains(response, "Paid editing order")
        self.assertContains(response, "Payment attempts")
        self.assertNotContains(response, "Order state 1")
