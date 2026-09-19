import json

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, SimpleTestCase

from core.views import forbidden, not_found, server_error


class ErrorRecoveryTests(SimpleTestCase):
    def setUp(self):
        self.requests = RequestFactory()

    def request(self, path):
        request = self.requests.get(path)
        request.user = AnonymousUser()
        return request

    def test_browser_errors_are_safe_and_actionable(self):
        secret = "private-project-title-that-must-not-render"
        cases = [
            (forbidden(self.request("/admin/private/"), Exception(secret)), 403, b"Return home"),
            (not_found(self.request("/client/private/"), Exception(secret)), 404, b"Return home"),
            (server_error(self.request("/orders/private/")), 500, b"Try again"),
        ]
        for response, status, action in cases:
            with self.subTest(status=status):
                self.assertEqual(response.status_code, status)
                self.assertContains(response, action, status_code=status)
                self.assertNotContains(response, secret, status_code=status)
        self.assertContains(cases[-1][0], 'href="/orders/private/"', status_code=500)

    def test_api_errors_return_generic_json(self):
        self.assertEqual(
            json.loads(forbidden(self.request("/api/private/"), Exception("secret")).content),
            {"error": "Permission denied."},
        )
        self.assertEqual(
            json.loads(not_found(self.request("/api/private/"), Exception("secret")).content),
            {"error": "Not found."},
        )
        response = server_error(self.request("/api/private/"))
        self.assertEqual(response.status_code, 500)
        self.assertEqual(json.loads(response.content), {"error": "Service temporarily unavailable."})

    def test_project_error_does_not_expose_identifiers_from_exception(self):
        secret = "s3://private-bucket/customer/object.mp4?signature=secret"
        response = not_found(self.request("/client/projects/missing/"), Exception(secret))
        self.assertNotContains(response, secret, status_code=404)
