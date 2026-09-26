import json
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from core.audit_reconciliation import audit_reconciliation_report
from core.models import Client, Project, User
from operations.models import AuditLog

PASSWORD = "Synthetic-Audit-72!Leaf"


class AuditReconciliationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "audit-reconcile@example.test", PASSWORD, name="Client"
        )
        self.profile = Client.objects.create(user=self.user)
        self.project = Project.objects.create(client=self.profile, title="Synthetic")

    def test_covered_records_with_safe_details_pass(self):
        AuditLog.objects.create(
            actor=self.user,
            action="client.registered",
            target_id=str(self.user.pk),
            detail={"status": "created"},
        )
        AuditLog.objects.create(
            actor=self.user,
            action="project.draft_created",
            target_id=str(self.project.pk),
            detail={},
        )
        report = audit_reconciliation_report()
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["critical_count"], 0)

    def test_missing_coverage_and_private_detail_fail_without_rendering_payload(self):
        AuditLog.objects.create(
            actor=self.user,
            action="synthetic.unsafe",
            target_id="synthetic",
            detail={"nested": {"password": "private-value"}},
        )
        report = audit_reconciliation_report()
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["critical"]["projects_missing_creation_event"], 1)
        self.assertEqual(report["critical"]["unsafe_detail_payloads"], 1)
        self.assertEqual(report["warnings"]["clients_without_registration_event"], 1)
        rendered = json.dumps(report)
        self.assertNotIn("private-value", rendered)
        self.assertNotIn(str(self.project.pk), rendered)


class AuditReconciliationCommandTests(TestCase):
    def test_command_fails_closed_with_aggregate_output(self):
        report = {
            "status": "fail",
            "code": "audit_reconciliation_failed",
            "event_count": 1,
            "critical": {"unsafe_detail_payloads": 1},
            "warnings": {},
            "critical_count": 1,
            "warning_count": 0,
        }
        output = StringIO()
        with patch(
            "core.management.commands.reconcile_audit_history.audit_reconciliation_report",
            return_value=report,
        ):
            with self.assertRaisesMessage(CommandError, "critical findings"):
                call_command("reconcile_audit_history", stdout=output)
        self.assertNotIn("secret", output.getvalue().lower())
