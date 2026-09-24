import uuid

from django.test import Client as Browser
from django.test import TestCase

from core.models import Client, Project, User
from operations.models import Admin, AuditLog, Notification, SupportMessage, SupportRequest

PASSWORD = "Synthetic-Support-72!Leaf"


class SupportWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.client_user = User.objects.create_user(
            "support-client@example.test", PASSWORD, name="Client"
        )
        cls.client_profile = Client.objects.create(user=cls.client_user)
        cls.other_user = User.objects.create_user(
            "support-other@example.test", PASSWORD, name="Other client"
        )
        cls.other_profile = Client.objects.create(user=cls.other_user)
        cls.project = Project.objects.create(client=cls.client_profile, title="Client project")
        cls.other_project = Project.objects.create(client=cls.other_profile, title="Other project")
        cls.admin = User.objects.create_user(
            "support-admin@example.test", PASSWORD, name="Admin", role="admin"
        )
        Admin.objects.create(user=cls.admin)

    def browser(self, user):
        browser = Browser()
        browser.force_login(user)
        return browser

    def open_request(self):
        key = uuid.uuid4()
        response = self.browser(self.client_user).post(
            "/client/support/create/",
            {
                "subject": "Help with my edit",
                "category": "project",
                "body": "Please check the project status.",
                "project": self.project.id,
                "request_key": key,
            },
        )
        support_request = SupportRequest.objects.get(request_key=key)
        self.assertRedirects(response, f"/support/{support_request.id}/")
        return support_request

    def test_client_opens_private_request_and_admin_is_notified(self):
        support_request = self.open_request()
        self.assertEqual(support_request.client, self.client_profile)
        self.assertEqual(support_request.project, self.project)
        self.assertEqual(support_request.messages.count(), 1)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.admin, event_key__startswith=f"support:{support_request.id}:opened"
            ).exists()
        )
        event = AuditLog.objects.get(action="support.request_opened")
        self.assertNotIn("Please check", str(event.detail))

    def test_cross_client_case_and_project_are_denied(self):
        support_request = self.open_request()
        other = self.browser(self.other_user)
        self.assertEqual(other.get(f"/support/{support_request.id}/").status_code, 404)
        self.assertEqual(
            other.post(
                "/client/support/create/",
                {
                    "subject": "Invalid project",
                    "category": "project",
                    "body": "Trying another project.",
                    "project": self.project.id,
                    "request_key": uuid.uuid4(),
                },
            ).status_code,
            403,
        )

    def test_internal_notes_are_hidden_and_shared_reply_notifies_client(self):
        support_request = self.open_request()
        admin = self.browser(self.admin)
        admin.post(
            f"/support/{support_request.id}/messages/",
            {"body": "Internal investigation.", "audience": "internal", "request_key": uuid.uuid4()},
        )
        admin.post(
            f"/support/{support_request.id}/messages/",
            {"body": "We are checking this.", "audience": "shared", "request_key": uuid.uuid4()},
        )
        client_response = self.browser(self.client_user).get(f"/support/{support_request.id}/")
        self.assertNotContains(client_response, "Internal investigation")
        self.assertContains(client_response, "We are checking this")
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.client_user, event_key__startswith="support-message:"
            ).exists()
        )

    def test_status_change_is_admin_only_retry_safe_and_closes_client_replies(self):
        support_request = self.open_request()
        client = self.browser(self.client_user)
        self.assertEqual(
            client.post(
                f"/support/{support_request.id}/status/", {"status": "resolved"}
            ).status_code,
            403,
        )
        admin = self.browser(self.admin)
        for _ in range(2):
            self.assertRedirects(
                admin.post(
                    f"/support/{support_request.id}/status/", {"status": "resolved"}
                ),
                f"/support/{support_request.id}/",
            )
        self.assertEqual(
            AuditLog.objects.filter(
                action="support.status_changed", target_id=str(support_request.id)
            ).count(),
            1,
        )
        self.assertEqual(
            Notification.objects.filter(
                event_key__startswith=f"support:{support_request.id}:status:resolved:at:"
            ).count(),
            1,
        )
        before = SupportMessage.objects.filter(support_request=support_request).count()
        response = client.post(
            f"/support/{support_request.id}/messages/",
            {"body": "One more reply.", "audience": "shared", "request_key": uuid.uuid4()},
        )
        self.assertRedirects(response, f"/support/{support_request.id}/")
        self.assertEqual(SupportMessage.objects.filter(support_request=support_request).count(), before)
