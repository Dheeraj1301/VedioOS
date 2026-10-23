from django.test import TestCase

from tests.assignment_fixtures import create_people


class BrandingTests(TestCase):
    def assert_brio_branding(self, response):
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("BRIO", content)
        self.assertNotIn("vedioos", content.lower())

    def test_public_and_authentication_pages_use_brio(self):
        for path in ["/", "/register/", "/login/", "/editor/signin/"]:
            with self.subTest(path=path):
                self.assert_brio_branding(self.client.get(path))

    def test_authenticated_workspace_uses_brio(self):
        _, client_profile, _ = create_people()
        self.client.force_login(client_profile.user)

        response = self.client.get("/client/")

        self.assert_brio_branding(response)
        self.assertContains(response, '<span class="brand-mark">B</span>BRIO', html=False)
