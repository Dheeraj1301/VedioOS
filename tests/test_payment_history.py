from django.test import Client as Browser
from django.test import TestCase

from core.models import Client, Order, Payment, Project, User
from operations.models import Admin

PASSWORD = "Synthetic-Payments-72!Leaf"


class PaymentHistoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            "ledger-owner@example.test", PASSWORD, name="Owner"
        )
        owner_profile = Client.objects.create(user=cls.owner)
        cls.project = Project.objects.create(client=owner_profile, title="Ledger project")
        cls.order = Order.objects.create(project=cls.project)
        cls.other = User.objects.create_user(
            "ledger-other@example.test", PASSWORD, name="Other"
        )
        other_profile = Client.objects.create(user=cls.other)
        other_project = Project.objects.create(client=other_profile, title="Other project")
        other_order = Order.objects.create(project=other_project)
        Payment.objects.create(
            order=other_order,
            provider="synthetic",
            provider_reference="other-payment",
            amount_minor=999,
            currency="INR",
            status="confirmed",
        )
        for index in range(55):
            Payment.objects.create(
                order=cls.order,
                provider="synthetic",
                provider_reference=f"owner-payment-{index}",
                amount_minor=1000 + index,
                currency="INR",
                status="confirmed" if index % 2 else "failed",
            )
        cls.admin = User.objects.create_user(
            "ledger-admin@example.test", PASSWORD, name="Admin", role="admin"
        )
        Admin.objects.create(user=cls.admin)

    def browser(self, user):
        browser = Browser()
        browser.force_login(user)
        return browser

    def test_client_history_is_scoped_filtered_and_stably_paginated(self):
        browser = self.browser(self.owner)
        first = browser.get("/client/payments/")
        self.assertEqual(len(first.context["payments"]), 50)
        first_ids = {payment.id for payment in first.context["payments"]}
        cursor = first.context["older_payment_cursor"]
        self.assertIsNotNone(cursor)
        newer = Payment.objects.create(
            order=self.order,
            provider="synthetic",
            provider_reference="newer-payment",
            amount_minor=2000,
            currency="INR",
            status="pending",
        )
        older = browser.get("/client/payments/", {"before": cursor})
        older_ids = {payment.id for payment in older.context["payments"]}
        self.assertEqual(len(older_ids), 5)
        self.assertFalse(first_ids & older_ids)
        self.assertNotIn(newer.id, older_ids)
        self.assertFalse(any(payment.provider_reference == "other-payment" for payment in first.context["payments"]))
        filtered = browser.get("/client/payments/", {"status": "pending"})
        self.assertEqual([payment.id for payment in filtered.context["payments"]], [newer.id])

    def test_admin_ledger_includes_all_clients_and_is_role_protected(self):
        self.assertEqual(Browser().get("/admin/payments/").status_code, 302)
        self.assertEqual(self.browser(self.owner).get("/admin/payments/").status_code, 403)
        response = self.browser(self.admin).get("/admin/payments/", {"status": "confirmed"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Payment ledger")
        self.assertTrue(
            any(payment.provider_reference == "other-payment" for payment in response.context["payments"])
        )

    def test_invalid_cursor_is_rejected(self):
        self.assertEqual(
            self.browser(self.owner).get("/client/payments/", {"before": "invalid"}).status_code,
            404,
        )
