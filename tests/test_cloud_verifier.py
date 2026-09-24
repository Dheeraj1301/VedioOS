from io import StringIO

from django.test import TestCase

from core.management.commands.verify_cloud import run_cloud_checks
from core.models import User


class CloudVerifierTests(TestCase):
    def test_current_auth_and_access_flow_is_reversible(self):
        output = StringIO()

        run_cloud_checks(output.write)

        report = output.getvalue()
        self.assertIn("client registration awaits email verification", report)
        self.assertIn("public editor registration is disabled", report)
        self.assertIn("administrator-issued editor ID login", report)
        self.assertIn("unassigned editor denied project access", report)
        self.assertIn("verification data rolled back", report)
        self.assertFalse(User.objects.filter(email__contains="verification-").exists())
