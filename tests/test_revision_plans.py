from django.test import TestCase

from core.commerce_forms import RevisionPlanForm
from core.context import NAV
from core.models import RevisionPlan
from tests.assignment_fixtures import create_people


class RevisionPlanTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin, cls.client_profile, cls.editors = create_people()

    def test_client_navigation_and_role_protection(self):
        self.assertIn(("Revisions", "/client/revisions/"), NAV["client"])
        self.client.force_login(self.client_profile.user)
        self.assertEqual(self.client.get("/client/revisions/").status_code, 200)
        self.assertEqual(self.client.get("/admin/pricing/revision-plans/1/").status_code, 403)

        self.client.force_login(self.admin)
        self.assertEqual(self.client.get("/client/revisions/").status_code, 403)

    def test_admin_pricing_always_exposes_three_revision_slots(self):
        self.client.force_login(self.admin)
        response = self.client.get("/admin/pricing/")
        self.assertContains(response, "Three revision plan slots")
        for slot in range(1, 4):
            self.assertContains(response, f"Configure revision plan {slot}")

    def test_admin_major_currency_input_persists_and_immediately_renders(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            "/admin/pricing/revision-plans/1/",
            {
                "name": "Focused polish",
                "price_minor": "249.50",
                "currency": "INR",
                "description": "One focused revision pass for timing and captions.",
                "active": "on",
            },
        )
        self.assertRedirects(response, "/admin/pricing/")
        plan = RevisionPlan.objects.get(slot=1)
        self.assertEqual(plan.price_minor, 24950)
        self.assertTrue(plan.active)

        self.client.force_login(self.client_profile.user)
        client_page = self.client.get("/client/revisions/")
        self.assertContains(client_page, "Focused polish")
        self.assertContains(client_page, "₹249.50")
        self.assertContains(client_page, "One focused revision pass")
        self.assertContains(client_page, 'aria-pressed="false" data-revision-plan', count=1)

    def test_unpublished_plans_are_hidden_from_clients(self):
        RevisionPlan.objects.create(
            slot=1,
            name="Private draft",
            price_minor=10000,
            currency="INR",
            description="Not ready for clients.",
            active=False,
        )
        self.client.force_login(self.client_profile.user)
        response = self.client.get("/client/revisions/")
        self.assertNotContains(response, "Private draft")
        self.assertContains(response, "Revision plans are being prepared")

    def test_publishing_requires_positive_price_currency_and_description(self):
        form = RevisionPlanForm(
            {
                "name": "Incomplete",
                "price_minor": "0",
                "currency": "INR",
                "description": "",
                "active": "on",
            },
            instance=RevisionPlan(slot=2),
        )
        self.assertFalse(form.is_valid())
        self.assertIn("price_minor", form.errors)
        self.assertIn("description", form.errors)
