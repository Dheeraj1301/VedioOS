import uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.test import TestCase
from django.utils import timezone

from core.models import Client, User
from operations.messages import post_message
from operations.models import AuditLog, EditorAssignment, Notification, ProjectMessage
from tests.assignment_fixtures import create_people, paid_project


class ProjectMessageTests(TestCase):
    def setUp(self):
        self.admin, self.client_profile, self.editors = create_people()
        self.client_user = self.client_profile.user
        self.project = paid_project(self.client_profile)
        self.assignment = EditorAssignment.objects.create(
            project=self.project, editor=self.editors[0], assigned_by=self.admin
        )

    def test_shared_and_internal_are_persisted_and_role_scoped(self):
        shared = post_message(
            self.client_user, self.project.id, "  Please trim at 00:03  ", "shared", uuid.uuid4()
        )
        self.assertEqual(shared.body, "Please trim at 00:03")
        self.assertEqual(Notification.objects.filter(project=self.project).count(), 2)
        private = post_message(
            self.admin, self.project.id, "<script>secret</script>", "internal", uuid.uuid4()
        )
        self.assertEqual(
            Notification.objects.filter(project=self.project, recipient=self.client_user).count(), 0
        )
        self.assertEqual(
            AuditLog.objects.filter(action="project.message_posted", target_id=str(private.id)).count(), 1
        )
        self.assertFalse(Notification.objects.filter(message__contains="secret").exists())
        self.client.force_login(self.client_user)
        page = self.client.get(f"/client/projects/{self.project.id}/")
        self.assertContains(page, "Please trim at 00:03")
        self.assertNotContains(page, "secret")
        self.client.force_login(self.editors[0].user)
        page = self.client.get(f"/editor/projects/{self.project.id}/")
        self.assertContains(page, "&lt;script&gt;secret&lt;/script&gt;")
        self.assertNotContains(page, "<script>secret</script>", html=False)

    def test_replay_is_idempotent_and_changed_payload_rejected(self):
        key = uuid.uuid4()
        first = post_message(self.client_user, self.project.id, "Hello", "shared", key)
        self.assertEqual(post_message(self.client_user, self.project.id, "Hello", "shared", key).id, first.id)
        with self.assertRaises(ValidationError):
            post_message(self.client_user, self.project.id, "Different", "shared", key)
        self.assertEqual(ProjectMessage.objects.count(), 1)
        self.assertEqual(Notification.objects.filter(project=self.project).count(), 2)

    def test_cross_client_unassigned_and_former_editor_denied(self):
        other = User.objects.create_user("message-other@example.test", "synthetic", name="Other")
        Client.objects.create(user=other)
        for outsider in (other, self.editors[1].user):
            with self.assertRaises(Http404):
                post_message(outsider, self.project.id, "No access", "shared", uuid.uuid4())
        self.assignment.ended_at = timezone.now()
        self.assignment.save()
        EditorAssignment.objects.create(project=self.project, editor=self.editors[1], assigned_by=self.admin)
        with self.assertRaises(Http404):
            post_message(self.editors[0].user, self.project.id, "Old access", "internal", uuid.uuid4())
        self.client.force_login(self.editors[0].user)
        self.assertEqual(self.client.get(f"/editor/projects/{self.project.id}/").status_code, 404)
        self.client.force_login(self.editors[1].user)
        self.assertEqual(self.client.get(f"/editor/projects/{self.project.id}/").status_code, 200)

    def test_client_cannot_forge_internal_note_or_empty_message(self):
        with self.assertRaises(PermissionDenied):
            post_message(self.client_user, self.project.id, "Private", "internal", uuid.uuid4())
        with self.assertRaises(ValidationError):
            post_message(self.client_user, self.project.id, "  ", "shared", uuid.uuid4())
        self.assertFalse(ProjectMessage.objects.exists())
        self.client.force_login(self.client_user)
        response = self.client.post(
            f"/orders/{self.project.id}/messages/",
            {"audience": "internal", "body": "Forged", "request_key": str(uuid.uuid4())},
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(ProjectMessage.objects.exists())

    def test_form_posts_and_anonymous_user_cannot_write(self):
        path = f"/orders/{self.project.id}/messages/"
        self.assertEqual(self.client.post(path, {}).status_code, 302)
        self.client.force_login(self.client_user)
        response = self.client.post(
            path,
            {"audience": "shared", "body": "A quick update", "request_key": str(uuid.uuid4())},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ProjectMessage.objects.get().body, "A quick update")
