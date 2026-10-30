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
        self.assertContains(response, 'src="/static/images/brio-logo-transparent.svg"', html=False)
        self.assertContains(response, 'alt="BRIO Logo"', html=False)
        self.assertContains(
            response, 'rel="icon" href="/static/images/brio-logo-transparent.svg"', html=False
        )
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
        self.assertContains(response, 'class="workspace-page workspace-role-client"', html=False)
        self.assertContains(response, "CLIENT WORKSPACE", count=1)
        self.assertContains(
            response,
            'class="workspace-label client-workspace-label"',
            html=False,
        )
        self.assertNotContains(response, "EDITOR WORKSPACE")
        self.assertIsNotNone(finders.find("images/brio-logo-transparent.svg"))
        self.assertIsNotNone(finders.find("brio-theme.css"))

    def test_client_login_uses_its_overlay_layout_only(self):
        client_login = self.client.get("/login/")
        registration = self.client.get("/register/")
        self.assertContains(registration, "Terms &amp; Conditions")
        self.assertContains(registration, "No Refund policy")
        self.assertContains(registration, "mandatory statutory rights")
        self.assertContains(registration, 'data-auth-entry')
        editor_login = self.client.get("/editor/signin/")

        self.assertContains(
            client_login,
            'class="auth-layout client-login-layout"',
            html=False,
        )
        self.assertContains(client_login, "Back to your next great edit.")
        self.assertNotContains(registration, "client-login-layout")
        self.assertNotContains(editor_login, "client-login-layout")
        self.assertContains(
            editor_login,
            'class="auth-layout editor-auth-layout"',
            html=False,
        )

    def test_availability_panels_fill_the_content_width(self):
        with open(finders.find("app.css"), encoding="utf-8") as stylesheet:
            css = stylesheet.read()

        self.assertIn(".availability-panel{width:100%;max-width:none;padding:34px}", css)
        self.assertIn(".availability-panel .stack-form{max-width:760px}", css)
