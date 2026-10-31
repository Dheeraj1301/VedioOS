import re
from html import unescape

from django.test import TestCase

from core.models import User


class AdminLinkTests(TestCase):
    def setUp(self):
        admin = User.objects.create_user("links-admin@example.test", "Synthetic-pass-123!", name="Links Admin", role="admin")
        self.client.force_login(admin)

    def test_dashboard_and_analytics_links_resolve(self):
        for page in ["/admin/", "/admin/analytics/"]:
            response = self.client.get(page)
            self.assertEqual(response.status_code, 200, page)
            hrefs = {unescape(href) for href in re.findall(r'href="(/admin/[^"#]*)"', response.content.decode())}
            self.assertTrue(hrefs, page)
            for href in sorted(hrefs):
                self.assertNotEqual(self.client.get(href).status_code, 404, f"{page} links to missing {href}")

    def test_orders_queue_links_apply_their_filters(self):
        response = self.client.get("/admin/orders/?payment=paid&workflow=awaiting_review")
        self.assertEqual(response.context["payment_filter"], "confirmed")
        self.assertEqual(response.context["workflow_filter"], "awaiting_review")
