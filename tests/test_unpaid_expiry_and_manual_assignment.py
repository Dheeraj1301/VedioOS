import uuid
from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import File, Payment, Project
from core.project_storage import expire_unpaid_projects, send_expiry_reminders
from operations.assignments import classify, manual_assign
from operations.availability import set_availability_override
from operations.models import AuditLog, Editor, EditorAssignment
from tests.assignment_fixtures import create_people, enable_test_policy, paid_project


class UnpaidExpiryTests(TestCase):
    def setUp(self):
        self.admin, self.client_profile, _editors = create_people()

    def unpaid(self, hours_old):
        project = paid_project(self.client_profile, paid=False)
        Project.objects.filter(pk=project.pk).update(created_at=timezone.now() - timedelta(hours=hours_old))
        File.objects.create(
            project=project, uploader=self.client_profile.user, filename="clip.mp4",
            object_key=f"edits/projects/{project.pk}/clip", storage_version="v1", content_type="video/mp4",
            size_bytes=10, sha256="0" * 64, category=File.Category.SOURCE, state="ready", expires_at=timezone.now(),
        )
        return project

    def remind(self, project, hours_ago):
        AuditLog.objects.create(action="project.expiry_reminder_sent", target_id=str(project.pk), detail={})
        AuditLog.objects.filter(action="project.expiry_reminder_sent", target_id=str(project.pk)).update(
            created_at=timezone.now() - timedelta(hours=hours_ago)
        )

    @patch("core.project_storage.delete_private_object_versions")
    def test_projects_unpaid_after_36_hours_are_removed_with_their_files(self, remove_versions):
        old, fresh = self.unpaid(37), self.unpaid(35)
        self.remind(old, 7)
        paid = paid_project(self.client_profile)
        Project.objects.filter(pk=paid.pk).update(created_at=timezone.now() - timedelta(hours=50))

        self.assertEqual(expire_unpaid_projects(), 1)
        old.refresh_from_db()
        fresh.refresh_from_db()
        paid.refresh_from_db()
        self.assertEqual(old.status, Project.Status.CANCELLED)
        self.assertIsNotNone(old.archived_at)
        remove_versions.assert_called_once_with(f"edits/projects/{old.pk}/clip")
        self.assertEqual(File.objects.get(project=old).state, "removed")
        self.assertTrue(AuditLog.objects.filter(action="project.expired_unpaid", target_id=str(old.pk)).exists())
        self.assertIsNone(fresh.archived_at)
        self.assertIsNone(paid.archived_at)

    @patch("core.project_storage.delete_private_object_versions")
    def test_a_checkout_started_within_the_hour_is_left_alone(self, remove_versions):
        project = self.unpaid(40)
        Payment.objects.create(order=project.order, provider="razorpay_live", provider_reference=uuid.uuid4().hex,
                               amount_minor=10000, currency="INR", status="pending")
        self.assertEqual(expire_unpaid_projects(), 0)
        remove_versions.assert_not_called()

    @override_settings(CRON_SECRET="synthetic-cron-secret")
    @patch("core.project_storage.delete_private_object_versions")
    def test_cron_endpoint_requires_the_vercel_secret(self, _remove_versions):
        self.remind(self.unpaid(37), 7)
        url = "/internal/expire-unpaid-projects/"
        self.assertEqual(self.client.get(url).status_code, 401)
        response = self.client.get(url, HTTP_AUTHORIZATION="Bearer synthetic-cron-secret")
        self.assertEqual(response.json(), {"expired_projects": 1})

    @override_settings(NOTIFICATION_EMAIL_ENABLED=True, DEFAULT_FROM_EMAIL="BRIO <brio4edits@gmail.com>",
                       EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_client_is_emailed_once_six_hours_before_expiry(self):
        due, early = self.unpaid(31), self.unpaid(29)
        self.assertEqual(send_expiry_reminders(), 1)
        self.assertEqual(send_expiry_reminders(), 0)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, [self.client_profile.user.email])
        self.assertEqual(message.from_email, "BRIO <brio4edits@gmail.com>")
        self.assertIn(due.title, message.body)
        self.assertIn("Payment pending", message.body)
        self.assertIn(f"/orders/{due.pk}/", message.body)
        self.assertFalse(AuditLog.objects.filter(action="project.expiry_reminder_sent", target_id=str(early.pk)).exists())

    @patch("core.project_storage.delete_private_object_versions")
    def test_a_project_is_never_removed_without_six_hours_notice(self, remove_versions):
        late = self.unpaid(40)
        self.assertEqual(expire_unpaid_projects(), 0)
        self.assertTrue(AuditLog.objects.filter(action="project.expiry_reminder_sent", target_id=str(late.pk)).exists())
        remove_versions.assert_not_called()
        AuditLog.objects.filter(action="project.expiry_reminder_sent").update(created_at=timezone.now() - timedelta(hours=6, minutes=1))
        self.assertEqual(expire_unpaid_projects(), 1)

    def test_project_page_warns_about_the_36_hour_rule(self):
        self.client.force_login(self.client_profile.user)
        page = self.client.get("/client/new-order/")
        self.assertContains(page, "Unpaid projects are deleted 36 hours after they are created")
        self.assertContains(page, 'class="notice-icon"')


@override_settings(DEBUG=True)
class AdminChoiceAssignmentTests(TestCase):
    def setUp(self):
        self.admin, self.client_profile, self.editors = create_people()
        enable_test_policy()
        self.project = paid_project(self.client_profile)
        classify(self.admin, self.project.id, "beginner", "Synthetic assessment", 0)

    def test_admin_can_choose_a_busy_or_different_level_editor_without_a_note(self):
        other = paid_project(self.client_profile, title="Busy work")
        classify(self.admin, other.id, "beginner", "Synthetic assessment", 0)
        busy = self.editors[0]
        manual_assign(self.admin, other.id, busy.pk, "First job")
        Editor.objects.filter(pk=busy.pk).update(proficiency_id="advanced")

        assignment = manual_assign(self.admin, self.project.id, busy.pk, "")
        self.assertEqual(assignment.editor_id, busy.pk)
        self.assertEqual(EditorAssignment.objects.filter(editor=busy, ended_at__isnull=True).count(), 2)

    def test_not_available_editors_still_cannot_be_chosen(self):
        editor = self.editors[1]
        set_availability_override(self.admin, editor.pk, Editor.AvailabilityOverride.NOT_AVAILABLE, "On leave")
        with self.assertRaises(ValidationError):
            manual_assign(self.admin, self.project.id, editor.pk, "")
