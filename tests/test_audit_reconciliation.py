import json
import uuid
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from core.audit_reconciliation import audit_reconciliation_report
from core.models import Client, Project, User
from operations.models import AuditLog, SupportMessage, SupportRequest

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

    def test_ticket_opening_event_covers_atomic_first_support_message(self):
        support_request = SupportRequest.objects.create(
            client=self.profile,
            subject="Account help",
            category="account",
            request_key=uuid.uuid4(),
        )
        SupportMessage.objects.create(
            support_request=support_request,
            author=self.user,
            audience="shared",
            body="Synthetic opening message",
            request_key=uuid.uuid4(),
        )
        AuditLog.objects.create(
            actor=self.user,
            action="support.request_opened",
            target_id=str(support_request.pk),
            detail={"category": "account"},
        )
        AuditLog.objects.create(
            actor=self.user,
            action="project.draft_created",
            target_id=str(self.project.pk),
            detail={},
        )

        report = audit_reconciliation_report()

        self.assertEqual(report["critical"]["support_messages_missing_event"], 0)

    def test_later_support_message_still_requires_its_own_event(self):
        support_request = SupportRequest.objects.create(
            client=self.profile,
            subject="Account help",
            category="account",
            request_key=uuid.uuid4(),
        )
        for index in range(2):
            SupportMessage.objects.create(
                support_request=support_request,
                author=self.user,
                audience="shared",
                body=f"Synthetic message {index}",
                request_key=uuid.uuid4(),
            )
        AuditLog.objects.create(
            actor=self.user,
            action="support.request_opened",
            target_id=str(support_request.pk),
            detail={"category": "account"},
        )

        report = audit_reconciliation_report()

        self.assertEqual(report["critical"]["support_messages_missing_event"], 1)

    def test_known_system_events_do_not_require_a_human_actor(self):
        AuditLog.objects.create(
            actor=None,
            action="identity.supabase_deleted",
            target_id=str(self.user.pk),
            detail={"provider": "supabase_auth"},
        )
        AuditLog.objects.create(
            actor=None,
            action="catalog.plan_publication_reconciled",
            target_id="1",
            detail={"reason": "legacy_publication_state"},
        )
        AuditLog.objects.create(
            actor=self.user,
            action="project.draft_created",
            target_id=str(self.project.pk),
            detail={},
        )

        report = audit_reconciliation_report()

        self.assertEqual(report["critical"]["unexpected_unattributed_events"], 0)


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
