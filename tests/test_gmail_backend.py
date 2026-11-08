import base64
from email import message_from_bytes
from unittest.mock import Mock, patch

from django.core.mail import EmailMessage
from django.test import SimpleTestCase, override_settings


@override_settings(
    EMAIL_BACKEND="core.gmail_backend.GmailAPIBackend",
    GMAIL_CLIENT_ID="synthetic-id",
    GMAIL_CLIENT_SECRET="synthetic-secret",
    GMAIL_REFRESH_TOKEN="synthetic-refresh",
)
class GmailAPIBackendTests(SimpleTestCase):
    @patch("core.gmail_backend.requests.post")
    def test_sends_the_message_through_gmail(self, post):
        post.side_effect = [Mock(json=lambda: {"access_token": "synthetic-access"}, raise_for_status=Mock()),
                            Mock(raise_for_status=Mock())]
        sent = EmailMessage("Hello", "Body text", "BRIO <brio4edits@gmail.com>", ["client@example.com"]).send()
        self.assertEqual(sent, 1)
        token_call, send_call = post.call_args_list
        self.assertEqual(token_call.kwargs["data"]["refresh_token"], "synthetic-refresh")
        self.assertEqual(send_call.kwargs["headers"], {"Authorization": "Bearer synthetic-access"})
        parsed = message_from_bytes(base64.urlsafe_b64decode(send_call.kwargs["json"]["raw"]))
        self.assertEqual(parsed["To"], "client@example.com")
        self.assertEqual(parsed["Subject"], "Hello")

    @patch("core.gmail_backend.requests.post")
    def test_a_rejected_token_raises_so_callers_can_retry(self, post):
        post.return_value = Mock(raise_for_status=Mock(side_effect=RuntimeError("401")))
        with self.assertRaises(RuntimeError):
            EmailMessage("Hello", "Body", "a@example.com", ["b@example.com"]).send()


class PrivacyPageTests(SimpleTestCase):
    databases = "__all__"

    def test_privacy_page_is_public(self):
        page = self.client.get("/privacy/")
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Privacy policy")
        self.assertContains(page, "brio4edits@gmail.com")
