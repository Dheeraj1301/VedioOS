from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase, override_settings

from core.email_verification import (
    VerificationCooldown,
    VerificationServiceUnavailable,
    check_verification_code,
    send_verification_email,
)


@override_settings(
    SUPABASE_AUTH_URL="https://project.supabase.co",
    SUPABASE_AUTH_PUBLISHABLE_KEY="sb_publishable_test",
    SUPABASE_AUTH_TIMEOUT_SECONDS=7,
)
class SupabaseEmailVerificationTests(SimpleTestCase):
    @patch("core.email_verification.requests.post")
    def test_send_requests_a_supabase_email_otp(self, post):
        post.return_value = Mock(status_code=200, json=lambda: {})

        send_verification_email("Client@Example.com")

        post.assert_called_once_with(
            "https://project.supabase.co/auth/v1/otp",
            json={"email": "Client@Example.com", "create_user": True},
            headers={
                "apikey": "sb_publishable_test",
                "Authorization": "Bearer sb_publishable_test",
            },
            timeout=7,
        )

    @patch("core.email_verification.requests.post")
    def test_rate_limit_is_reported_as_a_cooldown(self, post):
        post.return_value = Mock(status_code=429, json=lambda: {"code": "over_email_send_rate_limit"})

        with self.assertRaises(VerificationCooldown):
            send_verification_email("client@example.com")

    @patch("core.email_verification.requests.post")
    def test_matching_verified_email_is_accepted(self, post):
        post.return_value = Mock(
            status_code=200,
            json=lambda: {"user": {"email": "client@example.com"}},
        )

        result = check_verification_code("CLIENT@example.com", "123456")

        self.assertEqual(result, "verified")
        self.assertEqual(post.call_args.kwargs["json"]["type"], "email")

    @patch("core.email_verification.requests.post")
    def test_different_returned_email_is_rejected(self, post):
        post.return_value = Mock(
            status_code=200,
            json=lambda: {"user": {"email": "other@example.com"}},
        )

        self.assertEqual(check_verification_code("client@example.com", "123456"), "invalid")

    @patch("core.email_verification.requests.post")
    def test_expired_code_is_reported(self, post):
        post.return_value = Mock(status_code=403, json=lambda: {"code": "otp_expired"})

        self.assertEqual(check_verification_code("client@example.com", "123456"), "expired")

    @patch("core.email_verification.requests.post", side_effect=requests.Timeout)
    def test_network_failure_is_safe(self, _post):
        with self.assertRaises(VerificationServiceUnavailable):
            send_verification_email("client@example.com")

    @override_settings(SUPABASE_AUTH_PUBLISHABLE_KEY="")
    def test_missing_project_key_fails_closed(self):
        with self.assertRaises(VerificationServiceUnavailable):
            send_verification_email("client@example.com")
