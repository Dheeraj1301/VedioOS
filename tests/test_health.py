from unittest.mock import patch

from django.test import Client, TestCase


class HealthProbeTests(TestCase):
    def test_liveness_is_dependency_free_and_not_cached(self):
        with patch("core.health.database_ready", side_effect=AssertionError("must not run")):
            response = Client().get("/health/live/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_readiness_passes_with_current_database_and_migrations(self):
        response = Client().get("/health/ready/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_readiness_failure_is_generic_and_does_not_leak_exception(self):
        secret = "postgresql://private-user:private-password@private-host/database"
        with patch("core.health.database_ready", side_effect=RuntimeError(secret)):
            response = Client().get("/health/ready/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})
        self.assertNotIn(secret, response.content.decode())

    def test_probes_reject_mutating_methods(self):
        self.assertEqual(Client().post("/health/live/").status_code, 405)
        self.assertEqual(Client().post("/health/ready/").status_code, 405)
