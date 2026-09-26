import json
import uuid
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from core.delivery import transition
from core.delivery_reconciliation import delivery_reconciliation_report
from core.models import File, ProjectVersion, RevisionRequest
from tests.assignment_fixtures import create_people, enable_test_policy
from tests.test_delivery import delivery_fixture, ready_output


@override_settings(DEBUG=True)
class DeliveryReconciliationTests(TestCase):
    def setUp(self):
        self.admin, self.buyer, self.editors = create_people()
        enable_test_policy()
        self.editor = self.editors[0].user
        self.project = delivery_fixture(self.buyer, self.editors[0])

    def submit(self, previous=None):
        output = ready_output(self.project, self.editor)
        transition(self.editor, self.project.pk, "start")
        transition(
            self.editor,
            self.project.pk,
            "submit",
            file_id=output.pk,
            version_id=previous.pk if previous else None,
        )
        return self.project.versions.latest("number")

    def test_revision_and_acceptance_history_reconciles(self):
        first = self.submit()
        transition(self.buyer.user, self.project.pk, "revise", version_id=first.pk, note="Trim")
        second = self.submit(first)
        transition(self.buyer.user, self.project.pk, "accept", version_id=second.pk)
        report = delivery_reconciliation_report()
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["version_count"], 2)
        self.assertEqual(report["revision_count"], 1)

    def test_version_file_and_sequence_drift_are_detected(self):
        version = self.submit()
        foreign = File.objects.create(
            project=delivery_fixture(self.buyer, self.editors[1]),
            uploader=self.editors[1].user,
            filename="synthetic.mp4",
            object_key=f"synthetic/{uuid.uuid4()}",
            storage_version="test-version",
            content_type="video/mp4",
            size_bytes=32,
            sha256="a" * 64,
            category="draft",
            state="ready",
            expires_at=timezone.now(),
        )
        ProjectVersion.objects.filter(pk=version.pk).update(file=foreign, number=3)
        report = delivery_reconciliation_report()
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["critical"]["invalid_version_file"], 1)
        self.assertGreater(report["critical"]["invalid_version_sequence_or_project_state"], 0)
        self.assertNotIn(str(self.project.pk), json.dumps(report))

    def test_revision_and_acceptance_state_drift_are_detected(self):
        first = self.submit()
        transition(self.buyer.user, self.project.pk, "revise", version_id=first.pk, note="Trim")
        RevisionRequest.objects.filter(project=self.project).update(status="addressed")
        report = delivery_reconciliation_report()
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["critical"]["invalid_revision_state"], 1)
        self.assertEqual(report["critical"]["invalid_review_project_state"], 1)


class DeliveryReconciliationCommandTests(TestCase):
    def test_command_fails_closed_with_aggregate_output(self):
        report = {
            "status": "fail",
            "code": "delivery_reconciliation_failed",
            "version_count": 1,
            "revision_count": 0,
            "acceptance_count": 0,
            "critical": {"invalid_version_file": 1},
            "warnings": {},
            "critical_count": 1,
            "warning_count": 0,
        }
        output = StringIO()
        with patch(
            "core.management.commands.reconcile_delivery.delivery_reconciliation_report",
            return_value=report,
        ):
            with self.assertRaisesMessage(CommandError, "critical findings"):
                call_command("reconcile_delivery", stdout=output)
        self.assertNotIn("object_key", output.getvalue())
