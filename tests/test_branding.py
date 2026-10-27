from django.contrib.staticfiles import finders
from django.test import TestCase

from tests.assignment_fixtures import create_people


class BrandingTests(TestCase):
    def assert_brio_branding(self, response):
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("BRIO", content)
        self.assertNotIn("vedioos", content.lower())
        self.assertContains(response, 'class="brand-logo"', html=False)
        self.assertContains(response, 'src="/static/images/brio-logo.jpeg"', html=False)
        self.assertContains(response, 'alt="BRIO Logo"', html=False)
        self.assertContains(response, 'rel="icon" href="/static/images/brio-logo.jpeg"', html=False)
        self.assertNotContains(response, 'class="brand-mark"', html=False)

    def test_public_and_authentication_pages_use_brio(self):
        for path in ["/", "/register/", "/login/", "/editor/signin/"]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assert_brio_branding(response)
                if path != "/":
                    self.assertContains(response, 'class="auth-page"', html=False)

    def test_authenticated_workspace_uses_brio(self):
        _, client_profile, _ = create_people()
        self.client.force_login(client_profile.user)

        response = self.client.get("/client/")

        self.assert_brio_branding(response)
        self.assertContains(response, 'class="workspace-page"', html=False)
        self.assertIsNotNone(finders.find("images/brio-logo.jpeg"))
        self.assertIsNotNone(finders.find("brio-theme.css"))
