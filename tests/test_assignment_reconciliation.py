import json
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from core.assignment_reconciliation import assignment_reconciliation_report
from operations.assignments import assign_next, classify
from operations.models import AssignmentQueue, EditorAssignment, RoundRobinState
from tests.assignment_fixtures import create_people, enable_test_policy, paid_project


@override_settings(DEBUG=True)
class AssignmentReconciliationTests(TestCase):
    def setUp(self):
        self.admin, self.client_profile, self.editors = create_people()
        enable_test_policy()
        self.project = paid_project(self.client_profile)
        classify(self.admin, self.project.pk, "beginner", "Synthetic assessment", 0)

    def test_waiting_and_assigned_projects_reconcile(self):
        self.assertEqual(assignment_reconciliation_report()["status"], "pass")
        assign_next(self.project.pk, self.admin)
        report = assignment_reconciliation_report()
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["assignment_count"], 1)

    def test_queue_and_capacity_drift_are_detected(self):
        assignment = assign_next(self.project.pk, self.admin)
        AssignmentQueue.objects.filter(project=self.project).update(status="waiting")
        assignment.editor.workload_capacity = 0
        assignment.editor.save(update_fields=["workload_capacity"])
        report = assignment_reconciliation_report()
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["critical"]["queue_assignment_mismatch"], 1)
        self.assertEqual(report["critical"]["editors_over_capacity"], 1)

    def test_reviewed_open_project_without_queue_is_detected(self):
        AssignmentQueue.objects.filter(project=self.project).delete()
        report = assignment_reconciliation_report()
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["critical"]["reviewed_open_projects_missing_queue"], 1)

    def test_snapshot_and_rotation_drift_are_detected_without_identifiers(self):
        assignment = assign_next(self.project.pk, self.admin)
        EditorAssignment.objects.filter(pk=assignment.pk).update(policy_snapshot={})
        RoundRobinState.objects.filter(proficiency_id="beginner").update(last_editor=None)
        report = assignment_reconciliation_report()
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["critical"]["invalid_assignment_snapshot"], 1)
        self.assertEqual(report["critical"]["invalid_round_robin_pointer"], 1)
        self.assertNotIn(str(self.project.pk), json.dumps(report))


class AssignmentReconciliationCommandTests(TestCase):
    def test_command_fails_closed_with_aggregate_output(self):
        report = {
            "status": "fail",
            "code": "assignment_reconciliation_failed",
            "complexity_count": 1,
            "queue_count": 1,
            "assignment_count": 0,
            "rotation_count": 0,
            "critical": {"queue_assignment_mismatch": 1},
            "warnings": {},
            "critical_count": 1,
            "warning_count": 0,
        }
        output = StringIO()
        with patch(
            "core.management.commands.reconcile_assignments.assignment_reconciliation_report",
            return_value=report,
        ):
            with self.assertRaisesMessage(CommandError, "critical findings"):
                call_command("reconcile_assignments", stdout=output)
        self.assertNotIn("project_id", output.getvalue())
