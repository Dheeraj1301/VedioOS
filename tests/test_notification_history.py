from urllib.parse import parse_qs, urlparse

from django.test import TestCase
from django.utils import timezone

from core.models import Client, User
from operations.models import AuditLog, EditorAssignment, Notification
from tests.assignment_fixtures import create_people, paid_project


class NotificationHistoryTests(TestCase):
    def setUp(self):
        self.admin, self.client_profile, self.editors = create_people()
        self.client_user = self.client_profile.user
        self.project = paid_project(self.client_profile)

    def test_cursor_preserves_history_and_read_page(self):
        other = User.objects.create_user("notices-other@example.test", "synthetic", name="Other")
        other_client = Client.objects.create(user=other)
        other_project = paid_project(other_client)
        for number in range(55):
            Notification.objects.create(
                recipient=self.client_user,
                project=self.project if number % 2 else None,
                event_key=f"history-{number:02d}",
                message=f"notice-{number:02d}",
            )
        wrong_project = Notification.objects.create(
            recipient=self.client_user,
            project=other_project,
            event_key="wrong-project",
            message="hidden project notice",
        )
        Notification.objects.create(recipient=other, event_key="other-account", message="other notice")
        self.client.force_login(self.client_user)
        newest = self.client.get("/orders/notifications/")
        self.assertEqual(len(newest.context["notices"]), 50)
        self.assertContains(newest, "notice-54")
        self.assertNotContains(newest, "notice-00")
        self.assertNotContains(newest, "hidden project notice")
        self.assertNotContains(newest, "other notice")
        cursor = newest.context["older_notice_cursor"]
        self.assertTrue(cursor)
        Notification.objects.create(
            recipient=self.client_user, event_key="newer-account", message="newer notice"
        )
        older = self.client.get("/orders/notifications/", {"before": cursor})
        self.assertEqual(len(older.context["notices"]), 5)
        self.assertContains(older, "notice-00")
        self.assertNotContains(older, "newer notice")
        self.assertNotContains(older, "hidden project notice")
        oldest = older.context["notices"][-1]
        path = f"/orders/notifications/{oldest.pk}/read/"
        response = self.client.post(path, {"before": cursor})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(parse_qs(urlparse(response.url).query)["before"], [cursor])
        self.assertEqual(self.client.post(path, {"before": cursor}).status_code, 302)
        oldest.refresh_from_db()
        self.assertIsNotNone(oldest.read_at)
        self.assertEqual(
            AuditLog.objects.filter(action="notification.read", target_id=str(oldest.pk)).count(), 1
        )
        self.assertEqual(self.client.post(f"/orders/notifications/{wrong_project.pk}/read/").status_code, 404)
        self.assertEqual(self.client.get("/orders/notifications/?before=invalid").status_code, 404)
        self.assertEqual(self.client.post(path, {"before": "invalid"}).status_code, 404)

    def test_former_editor_loses_project_notices_but_keeps_account_notices(self):
        assignment = EditorAssignment.objects.create(
            project=self.project, editor=self.editors[0], assigned_by=self.admin
        )
        project_notice = Notification.objects.create(
            recipient=self.editors[0].user,
            project=self.project,
            event_key="editor-project-notice",
            message="Assigned project update",
        )
        Notification.objects.create(
            recipient=self.editors[0].user, event_key="editor-account-notice", message="Account update"
        )
        assignment.ended_at = timezone.now()
        assignment.save()
        EditorAssignment.objects.create(project=self.project, editor=self.editors[1], assigned_by=self.admin)
        self.client.force_login(self.editors[0].user)
        page = self.client.get("/orders/notifications/")
        self.assertContains(page, "Account update")
        self.assertNotContains(page, "Assigned project update")
        self.assertEqual(
            self.client.post(f"/orders/notifications/{project_notice.pk}/read/").status_code, 404
        )
