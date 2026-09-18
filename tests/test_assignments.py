import uuid
from datetime import timedelta
from io import StringIO

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import File, Order
from core.permissions import visible_projects
from operations.assignments import (
    assign_next,
    change_availability,
    classify,
    configure_editor,
    manual_assign,
    process_queue,
    save_policy,
)
from operations.models import (
    AssignmentPolicy,
    AssignmentQueue,
    AuditLog,
    EditorAssignment,
    Notification,
    ProjectComplexity,
    RoundRobinState,
)
from tests.assignment_fixtures import create_people, enable_test_policy, paid_project


@override_settings(DEBUG=True)
class AssignmentTests(TestCase):
    def setUp(self):
        self.admin, self.client_profile, self.editors = create_people()
        enable_test_policy()

    def queue(self, level="beginner"):
        project = paid_project(self.client_profile)
        classify(self.admin, project.id, level, "Synthetic admin assessment", 0)
        return project

    def test_overdue_alerts_only_for_recorded_paid_open_deadlines(self):
        overdue = paid_project(self.client_profile)
        overdue.expected_delivery_at = timezone.now() - timedelta(hours=1)
        overdue.save()
        future = paid_project(self.client_profile)
        future.expected_delivery_at = timezone.now() + timedelta(hours=1)
        future.save()
        unpaid = paid_project(self.client_profile, paid=False)
        unpaid.expected_delivery_at = timezone.now() - timedelta(hours=1)
        unpaid.save()
        for _ in range(2):
            call_command("notify_overdue", stdout=StringIO())
        self.assertEqual(Notification.objects.filter(recipient=self.admin, project=overdue).count(), 1)
        self.assertEqual(
            AuditLog.objects.filter(action="deadline.overdue_alerted", target_id=str(overdue.id)).count(), 1
        )
        self.assertFalse(Notification.objects.filter(project__in=[future, unpaid]).exists())
        self.client.force_login(self.admin)
        self.assertContains(self.client.get("/admin/"), "Past recorded deadline")
        self.assertContains(self.client.get("/admin/projects/?queue=unassigned"), overdue.title)

    def test_unpaid_and_forged_payment_state_rejected(self):
        project = paid_project(self.client_profile, paid=False)
        with self.assertRaises(ValidationError):
            classify(self.admin, project.id, "beginner", "Unpaid", 0)
        project.status, project.payment_completed_at = "payment_completed", timezone.now()
        project.save()
        Order.objects.filter(project=project).update(payment_status="confirmed")
        with self.assertRaises(ValidationError):
            classify(self.admin, project.id, "beginner", "Forged payment", 0)
        self.assertFalse(AssignmentQueue.objects.exists())

    @override_settings(DEBUG=False)
    def test_sandbox_payment_cannot_fund_production_assignment(self):
        project = paid_project(self.client_profile)
        with self.assertRaises(ValidationError):
            classify(self.admin, project.id, "beginner", "Sandbox payment", 0)

    def test_default_policy_disabled_and_incomplete_configuration_rejected(self):
        AssignmentPolicy.objects.filter(pk=1).update(manual_enabled=False, automatic_enabled=False)
        project = self.queue()
        with self.assertRaises(ValidationError):
            assign_next(project.id)
        with self.assertRaises(ValidationError):
            manual_assign(self.admin, project.id, self.editors[0].id, "Test")
        with self.assertRaises(ValidationError):
            save_policy(self.admin, {"automatic_enabled": True})

    def test_rotation_does_not_restart_when_first_editor_finishes(self):
        first, second, third = [self.queue() for _ in range(3)]
        self.assertEqual(assign_next(first.id).editor_id, self.editors[0].id)
        self.assertEqual(assign_next(second.id).editor_id, self.editors[1].id)
        first.status = "completed"
        first.save()
        EditorAssignment.objects.filter(project=first).update(ended_at=timezone.now())
        self.assertEqual(assign_next(third.id).editor_id, self.editors[2].id)
        state = RoundRobinState.objects.get(proficiency_id="beginner")
        self.assertEqual(state.sequence, 3)
        self.assertEqual(assign_next(self.queue().id).editor_id, self.editors[0].id)

    def test_skip_and_wait_policy_and_durable_retry(self):
        change_availability(self.editors[0].user, "busy")
        project = self.queue()
        AssignmentPolicy.objects.filter(pk=1).update(busy_strategy="wait")
        self.assertIsNone(assign_next(project.id))
        queue = AssignmentQueue.objects.get(project=project)
        self.assertIn("Editor 1", queue.blocked_reason)
        self.assertEqual(RoundRobinState.objects.get(proficiency_id="beginner").sequence, 0)
        AssignmentPolicy.objects.filter(pk=1).update(busy_strategy="skip")
        self.assertEqual(assign_next(project.id).editor_id, self.editors[1].id)
        queue.refresh_from_db()
        self.assertEqual(queue.status, "assigned")
        self.assertEqual(queue.attempts, 2)

    def test_no_capacity_and_inactive_approval_are_excluded(self):
        for editor in self.editors:
            editor.workload_capacity = None
            editor.save()
        project = self.queue()
        self.assertIsNone(assign_next(project.id))
        self.assertIn("capacity", AssignmentQueue.objects.get(project=project).blocked_reason)
        editor = self.editors[0]
        editor.workload_capacity, editor.approved = 1, False
        editor.save()
        self.assertIsNone(assign_next(project.id))
        editor.approved = True
        editor.save()
        editor.user.is_active = False
        editor.user.save()
        self.assertIsNone(assign_next(project.id))

    def test_retries_and_availability_changes_preserve_pointer(self):
        project = self.queue()
        first = assign_next(project.id)
        self.assertEqual(assign_next(project.id).id, first.id)
        change_availability(self.editors[0].user, "offline")
        change_availability(self.editors[0].user, "available")
        self.assertEqual(RoundRobinState.objects.get(proficiency_id="beginner").sequence, 1)
        self.assertEqual(EditorAssignment.objects.filter(project=project).count(), 1)

    def test_separate_groups_no_cross_level_fallback(self):
        project = self.queue("advanced")
        self.assertIsNone(assign_next(project.id))
        self.assertEqual(RoundRobinState.objects.get(proficiency_id="advanced").sequence, 0)
        self.assertEqual(RoundRobinState.objects.get(proficiency_id="beginner").sequence, 0)
        with self.assertRaises(ValidationError):
            manual_assign(self.admin, project.id, self.editors[0].id, "Wrong level")

    def test_reassignment_revokes_old_access_preserves_deadline_and_history(self):
        project = self.queue()
        deadline = timezone.now() + timezone.timedelta(hours=24)
        project.expected_delivery_at = deadline
        project.save()
        first = manual_assign(self.admin, project.id, self.editors[0].id, "First editor")
        file = File.objects.create(
            project=project,
            uploader=self.client_profile.user,
            filename="synthetic.mp4",
            object_key=str(uuid.uuid4()),
            content_type="video/mp4",
            size_bytes=1,
            sha256="a" * 64,
            category="source",
            state="ready",
            expires_at=timezone.now(),
        )
        second = manual_assign(self.admin, project.id, self.editors[1].id, "Reassign", first.id)
        self.assertNotEqual(first.id, second.id)
        self.assertFalse(visible_projects(self.editors[0].user).filter(pk=project.id).exists())
        self.assertTrue(visible_projects(self.editors[1].user).filter(pk=project.id).exists())
        self.client.force_login(self.editors[0].user)
        self.assertEqual(self.client.get(f"/api/projects/{project.id}/").status_code, 404)
        self.assertEqual(self.client.post(f"/api/files/{file.id}/download/").status_code, 404)
        project.refresh_from_db()
        self.assertEqual(project.expected_delivery_at, deadline)
        self.assertEqual(project.assignments.count(), 2)
        self.assertFalse(RoundRobinState.objects.exclude(sequence=0).exists())

    def test_manual_pointer_advance_and_stale_reassignment(self):
        AssignmentPolicy.objects.filter(pk=1).update(manual_pointer="advance")
        project = self.queue()
        first = manual_assign(self.admin, project.id, self.editors[1].id, "Manual")
        self.assertEqual(
            RoundRobinState.objects.get(proficiency_id="beginner").last_editor_id, self.editors[1].id
        )
        self.assertEqual(assign_next(self.queue().id).editor_id, self.editors[2].id)
        with self.assertRaises(ValidationError):
            manual_assign(self.admin, project.id, self.editors[0].id, "Stale", uuid.uuid4())
        self.assertEqual(manual_assign(self.admin, project.id, self.editors[1].id, "Retry").id, first.id)

    def test_capacity_cannot_drop_below_active_work(self):
        project = self.queue()
        assign_next(project.id)
        with self.assertRaises(ValidationError):
            configure_editor(
                self.admin,
                self.editors[0].id,
                approved=False,
                proficiency="beginner",
                capacity=1,
                status="available",
                reason="Revoke",
            )
        with self.assertRaises(ValidationError):
            manual_assign(self.admin, self.queue().id, self.editors[0].id, "Overbook")

    def test_review_and_revision_work_hold_capacity(self):
        project = self.queue()
        assignment = assign_next(project.id)
        for status in ["awaiting_review", "revision_requested", "revision_in_progress"]:
            project.status = status
            project.save()
            with self.assertRaises(ValidationError):
                manual_assign(self.admin, self.queue().id, assignment.editor_id, "Overbook")

    def test_stale_complexity_and_nonadmin_denied(self):
        project = self.queue()
        with self.assertRaises(ValidationError):
            classify(self.admin, project.id, "advanced", "Stale", 0)
        with self.assertRaises(PermissionDenied):
            classify(self.client_profile.user, project.id, "advanced", "Escalate", 1)
        for user in [self.client_profile.user, self.editors[0].user]:
            self.client.force_login(user)
            self.assertEqual(
                self.client.post(f"/admin/assignments/{project.id}/", {"action": "automatic"}).status_code,
                403,
            )
        self.assertEqual(ProjectComplexity.objects.get(project=project).proficiency_id, "beginner")

    def test_new_roster_members_do_not_reset_rotation(self):
        assign_next(self.queue().id)
        self.editors[0].proficiency_id = "advanced"
        self.editors[0].save()
        self.assertEqual(assign_next(self.queue().id).editor_id, self.editors[1].id)

    def test_admin_views_queue_and_audit(self):
        project = self.queue()
        self.client.force_login(self.admin)
        self.assertContains(self.client.get("/admin/assignments/?status=waiting"), project.title)
        self.assertContains(self.client.get(f"/admin/assignments/{project.id}/"), "Review complexity")
        self.assertContains(
            self.client.get(f"/admin/editors/{self.editors[0].id}/operations/"), "Maximum concurrent"
        )
        self.assertEqual(process_queue(self.admin), (1, 0))
        self.assertTrue(AuditLog.objects.filter(action="project.assigned", target_id=project.id).exists())
        self.assertTrue(
            AuditLog.objects.filter(action="project.complexity_reviewed", target_id=project.id).exists()
        )
