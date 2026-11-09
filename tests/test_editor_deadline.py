from datetime import timedelta

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from operations.assignments import classify, manual_assign
from operations.editor_deadline import attach_deadlines, send_deadline_emails
from operations.models import AuditLog, EditorAssignment
from tests.assignment_fixtures import create_people, enable_test_policy, paid_project

EMAIL = dict(NOTIFICATION_EMAIL_ENABLED=True, DEFAULT_FROM_EMAIL="BRIO <brio4edits@gmail.com>",
             EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", DEBUG=True)


@override_settings(**EMAIL)
class EditorDeadlineTests(TestCase):
    def setUp(self):
        self.admin, self.client_profile, self.editors = create_people()
        enable_test_policy()
        self.project = paid_project(self.client_profile, title="Wedding reel")
        classify(self.admin, self.project.id, "beginner", "Synthetic assessment", 0)

    def assign(self):
        with self.captureOnCommitCallbacks(execute=True):
            return manual_assign(self.admin, self.project.id, self.editors[0].pk, "")

    def age(self, assignment, hours):
        EditorAssignment.objects.filter(pk=assignment.pk).update(created_at=timezone.now() - timedelta(hours=hours))

    def test_editor_is_emailed_on_assignment_with_the_24_hour_deadline(self):
        self.assign()
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, [self.editors[0].user.email])
        self.assertIn("Wedding reel", message.subject)
        self.assertIn("24 hours", message.body)
        self.assertEqual(send_deadline_emails(), 0)

    def test_reminders_go_out_once_at_12_and_6_hours_left(self):
        assignment = self.assign()
        self.age(assignment, 12.5)
        self.assertEqual(send_deadline_emails(), 1)
        self.assertIn("12 hours left", mail.outbox[-1].subject)
        self.assertEqual(send_deadline_emails(), 0)
        self.age(assignment, 18.5)
        self.assertEqual(send_deadline_emails(), 1)
        self.assertIn("6 hours left", mail.outbox[-1].subject)
        self.assertEqual(send_deadline_emails(), 0)
        self.assertEqual(AuditLog.objects.filter(action="assignment.deadline_email").count(), 3)

    def test_a_late_sweep_sends_only_the_latest_reminder(self):
        with self.captureOnCommitCallbacks(execute=False):
            assignment = manual_assign(self.admin, self.project.id, self.editors[0].pk, "")
        self.age(assignment, 19)
        self.assertEqual(send_deadline_emails(), 1)
        self.assertIn("6 hours left", mail.outbox[0].subject)

    def test_dashboards_show_the_countdown(self):
        assignment = self.assign()
        row = attach_deadlines([self.project])[0]
        self.assertEqual(row.editor_deadline_at, assignment.created_at + timedelta(hours=24))
        self.client.force_login(self.editors[0].user)
        self.assertContains(self.client.get("/editor/"), "data-deadline-left")
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(f"/admin/assignments/{self.project.id}/"), "data-deadline-left")
        self.assertContains(self.client.get("/admin/assignments/?status=assigned"), "data-deadline-left")


@override_settings(VISIT_SWEEP_ENABLED=True, **EMAIL)
class VisitSweepTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        self.admin, self.client_profile, self.editors = create_people()
        enable_test_policy()
        self.project = paid_project(self.client_profile, title="Visit sweep reel")
        classify(self.admin, self.project.id, "beginner", "Synthetic assessment", 0)
        with self.captureOnCommitCallbacks(execute=False):
            self.assignment = manual_assign(self.admin, self.project.id, self.editors[0].pk, "")
        EditorAssignment.objects.filter(pk=self.assignment.pk).update(created_at=timezone.now() - timedelta(hours=13))

    def test_any_page_visit_sends_due_reminders_once_per_interval(self):
        self.client.get("/")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("12 hours left", mail.outbox[0].subject)
        EditorAssignment.objects.filter(pk=self.assignment.pk).update(created_at=timezone.now() - timedelta(hours=19))
        self.client.get("/")
        self.assertEqual(len(mail.outbox), 1)
