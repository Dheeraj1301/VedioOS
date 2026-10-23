import uuid

from django.test import TestCase

from core.models import Client, Project, User
from operations.messages import post_message
from operations.models import EditorAssignment, ProjectMessage
from tests.assignment_fixtures import create_people, paid_project


class ClientCommunicationTests(TestCase):
    def setUp(self):
        self.admin, self.client_profile, self.editors = create_people()
        self.client_user = self.client_profile.user
        self.ongoing = paid_project(self.client_profile, title="Ongoing edit")
        self.completed = paid_project(self.client_profile, title="Completed edit")
        self.completed.status = Project.Status.COMPLETED
        self.completed.save(update_fields=["status"])
        self.assignment = EditorAssignment.objects.create(
            project=self.ongoing, editor=self.editors[0], assigned_by=self.admin
        )
        ProjectMessage.objects.create(
            project=self.completed,
            author=self.admin,
            audience=ProjectMessage.Audience.SHARED,
            body="Your completed delivery history",
            request_key=uuid.uuid4(),
        )
        self.client.force_login(self.client_user)

    def test_sidebar_order_list_grouping_and_latest_preview(self):
        post_message(
            self.client_user,
            self.ongoing.id,
            "Latest ongoing update",
            ProjectMessage.Audience.SHARED,
            uuid.uuid4(),
        )
        response = self.client.get("/client/communication/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ongoing")
        self.assertContains(response, "Completed")
        self.assertContains(response, "Latest ongoing update")
        self.assertContains(response, "Your completed delivery history")
        content = response.content.decode()
        self.assertLess(content.index("Project Communication"), content.index("Support"))

    def test_project_detail_no_longer_contains_client_communication(self):
        response = self.client.get(f"/client/projects/{self.ongoing.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Conversation")
        self.assertNotContains(response, "Message to client and team")

    def test_ongoing_send_editor_reply_and_session_reload_are_persisted(self):
        path = f"/client/communication/{self.ongoing.id}/"
        response = self.client.get(path)
        request_key = response.context["message_request_key"]
        sent = self.client.post(
            f"/orders/{self.ongoing.id}/messages/",
            {
                "audience": ProjectMessage.Audience.SHARED,
                "body": "Client persisted message",
                "request_key": request_key,
            },
        )
        self.assertRedirects(sent, path)
        post_message(
            self.editors[0].user,
            self.ongoing.id,
            "Editor persisted reply",
            ProjectMessage.Audience.SHARED,
            uuid.uuid4(),
        )
        self.client.logout()
        self.client.force_login(self.client_user)
        reloaded = self.client.get(path)
        self.assertContains(reloaded, "Client persisted message")
        self.assertContains(reloaded, "Editor persisted reply")
        self.assertContains(reloaded, self.editors[0].user.name)
        self.assertContains(reloaded, "Client and team")

    def test_phone_number_sequences_are_rejected_but_broken_sequences_are_allowed(self):
        path = f"/client/communication/{self.ongoing.id}/"
        page = self.client.get(path)
        self.assertContains(page, "data-digit-restricted", html=False)
        self.assertContains(
            page,
            "Phone numbers are restricted. Please do not enter more than 5 consecutive numbers.",
        )
        blocked = self.client.post(
            f"/orders/{self.ongoing.id}/messages/",
            {
                "audience": ProjectMessage.Audience.SHARED,
                "body": "Call me at 9876543210",
                "request_key": page.context["message_request_key"],
            },
        )
        self.assertEqual(blocked.status_code, 400)
        self.assertContains(
            blocked,
            "Phone numbers are restricted. Please do not enter more than 5 consecutive numbers.",
            status_code=400,
        )
        self.assertFalse(ProjectMessage.objects.filter(body__contains="9876543210").exists())

        allowed = self.client.post(
            f"/orders/{self.ongoing.id}/messages/",
            {
                "audience": ProjectMessage.Audience.SHARED,
                "body": "Reference 12345 67890 and 123-456",
                "request_key": uuid.uuid4(),
            },
        )
        self.assertRedirects(allowed, path)
        self.assertTrue(
            ProjectMessage.objects.filter(
                project=self.ongoing,
                body="Reference 12345 67890 and 123-456",
            ).exists()
        )

    def test_completed_history_is_read_only_in_ui_and_backend(self):
        path = f"/client/communication/{self.completed.id}/"
        response = self.client.get(path)
        self.assertContains(response, "Your completed delivery history")
        self.assertContains(response, "This project is complete. Messaging is disabled.")
        self.assertNotContains(response, "Message to client and team")
        self.assertNotContains(response, ">Send message<", html=False)
        before = ProjectMessage.objects.filter(project=self.completed).count()
        blocked = self.client.post(
            f"/orders/{self.completed.id}/messages/",
            {
                "audience": ProjectMessage.Audience.SHARED,
                "body": "Must not be saved",
                "request_key": uuid.uuid4(),
            },
            follow=True,
        )
        self.assertContains(blocked, "This project is complete. Messaging is disabled.")
        self.assertEqual(ProjectMessage.objects.filter(project=self.completed).count(), before)

    def test_cross_client_conversation_is_not_visible(self):
        outsider = User.objects.create_user(
            "communication-outsider@example.test", "synthetic", name="Outsider"
        )
        Client.objects.create(user=outsider)
        self.client.force_login(outsider)
        self.assertEqual(
            self.client.get(f"/client/communication/{self.ongoing.id}/").status_code,
            404,
        )
