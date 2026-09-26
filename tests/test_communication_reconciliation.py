import json
import uuid
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from core.communication_reconciliation import communication_reconciliation_report
from operations.messages import post_message
from operations.models import Admin, EditorAssignment, ProjectMessage, SupportMessage, SupportRequest
from operations.support import create_support_request, post_support_message
from tests.assignment_fixtures import create_people, paid_project


class CommunicationReconciliationTests(TestCase):
    def setUp(self):
        self.admin, self.client_profile, self.editors = create_people()
        Admin.objects.create(user=self.admin)
        self.project = paid_project(self.client_profile)
        EditorAssignment.objects.create(
            project=self.project, editor=self.editors[0], assigned_by=self.admin
        )
        self.project_message = post_message(
            self.client_profile.user,
            self.project.pk,
            "Please check the opening.",
            "shared",
            uuid.uuid4(),
        )
        self.support_request = create_support_request(
            self.client_profile.user,
            "Project help",
            "project",
            "Please check the current status.",
            self.project.pk,
            uuid.uuid4(),
        )
        post_support_message(
            self.admin,
            self.support_request.pk,
            "We are checking this.",
            "shared",
            uuid.uuid4(),
        )

    def test_project_and_support_messages_reconcile(self):
        report = communication_reconciliation_report()
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["project_message_count"], 1)
        self.assertEqual(report["support_message_count"], 2)

    def test_client_internal_project_message_is_detected(self):
        ProjectMessage.objects.filter(pk=self.project_message.pk).update(audience="internal")
        report = communication_reconciliation_report()
        self.assertEqual(report["status"], "fail")
        self.assertEqual(
            report["critical"]["invalid_project_message_author_or_audience"], 1
        )
        self.assertNotIn("Please check", json.dumps(report))

    def test_support_owner_and_opening_message_drift_are_detected(self):
        other_admin, other_client, _ = create_people()
        other_project = paid_project(other_client)
        SupportRequest.objects.filter(pk=self.support_request.pk).update(project=other_project)
        opening = self.support_request.messages.order_by("created_at", "id").first()
        SupportMessage.objects.filter(pk=opening.pk).update(author=other_admin, audience="internal")
        report = communication_reconciliation_report()
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["critical"]["invalid_support_request"], 1)
        self.assertEqual(report["critical"]["missing_or_invalid_support_opening_message"], 1)


class CommunicationReconciliationCommandTests(TestCase):
    def test_command_fails_closed_with_aggregate_output(self):
        report = {
            "status": "fail",
            "code": "communication_reconciliation_failed",
            "project_message_count": 1,
            "support_request_count": 1,
            "support_message_count": 1,
            "critical": {"invalid_support_request": 1},
            "warnings": {},
            "critical_count": 1,
            "warning_count": 0,
        }
        output = StringIO()
        with patch(
            "core.management.commands.reconcile_communications.communication_reconciliation_report",
            return_value=report,
        ):
            with self.assertRaisesMessage(CommandError, "critical findings"):
                call_command("reconcile_communications", stdout=output)
        self.assertNotIn("message body", output.getvalue())
