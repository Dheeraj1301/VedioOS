from datetime import timedelta
from unittest.mock import patch

from django.contrib.sessions.models import Session
from django.test import Client as Browser
from django.test import TestCase
from django.utils import timezone

from core.email_verification import VerificationServiceUnavailable
from core.models import AuthAttempt, Client, User
from operations.models import AuditLog, Editor

OLD_PASSWORD = "Old-Password-72!Leaf"
NEW_PASSWORD = "New-Password-83!Tree"


class PasswordResetWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            "reset-client@example.test",
            OLD_PASSWORD,
            name="Reset client",
            is_active=True,
            email_verified_at=timezone.now(),
        )
        Client.objects.create(user=cls.user)
        cls.editor_user = User.objects.create_user(
            "reset-editor@example.test",
            OLD_PASSWORD,
            name="Reset editor",
            role="editor",
            is_active=True,
        )
        Editor.objects.create(user=cls.editor_user, login_id="RESET-EDITOR")

    def reset_rate_limit(self):
        AuthAttempt.objects.all().delete()

    def request_code(self, browser=None):
        browser = browser or Browser()
        with patch("core.views.send_password_reset_email") as send:
            response = browser.post("/password-reset/", {"email": self.user.email})
        self.assertRedirects(response, "/password-reset/code/")
        send.assert_called_once_with(self.user.email)
        return browser

    def verify_code(self, browser):
        self.reset_rate_limit()
        with patch(
            "core.views.check_password_reset_code",
            return_value=("verified", "encrypted-recovery-grant"),
        ) as verify:
            response = browser.post("/password-reset/code/", {"code": "123456"})
        self.assertRedirects(response, "/password-reset/new/")
        verify.assert_called_once_with(self.user.email, "123456")

    def test_login_links_to_three_step_client_reset(self):
        login = Browser().get("/login/")
        self.assertContains(login, "Forgot password?")
        self.assertNotContains(Browser().get("/editor/signin/"), "Forgot password?")
        request_page = Browser().get("/password-reset/")
        self.assertContains(request_page, "Step 1 of 3")
        self.assertContains(request_page, 'autocomplete="email"')

    def test_request_is_non_enumerating_and_excludes_editor_accounts(self):
        for email in ["missing@example.test", self.editor_user.email]:
            browser = Browser()
            with patch("core.views.send_password_reset_email") as send:
                response = browser.post("/password-reset/", {"email": email}, follow=True)
            self.assertContains(response, "If an eligible client account matches that email")
            send.assert_not_called()
            self.reset_rate_limit()

        with patch(
            "core.views.send_password_reset_email",
            side_effect=VerificationServiceUnavailable("provider unavailable"),
        ):
            response = Browser().post("/password-reset/", {"email": self.user.email}, follow=True)
        self.assertContains(response, "If an eligible client account matches that email")

    def test_invalid_expired_and_unavailable_codes_do_not_create_grant(self):
        for result, text in [
            ("invalid", "That code is invalid"),
            ("expired", "That code has expired"),
            ("locked", "Too many incorrect attempts"),
        ]:
            browser = self.request_code()
            self.reset_rate_limit()
            with patch("core.views.check_password_reset_code", return_value=(result, None)):
                response = browser.post("/password-reset/code/", {"code": "123456"}, follow=True)
            self.assertContains(response, text)
            self.assertNotIn("password_reset_user_id", browser.session)
            self.reset_rate_limit()

    def test_verified_code_resets_password_revokes_session_and_allows_login(self):
        signed_in = Browser()
        self.assertRedirects(
            signed_in.post("/login/", {"username": self.user.email, "password": OLD_PASSWORD}),
            "/dashboard/",
            fetch_redirect_response=False,
        )
        self.user.refresh_from_db()
        previous_session_key = self.user.active_session_key
        self.assertTrue(Session.objects.filter(session_key=previous_session_key).exists())

        reset = self.request_code()
        self.verify_code(reset)
        page = reset.get("/password-reset/new/")
        self.assertContains(page, "Step 3 of 3")
        self.assertContains(page, "Confirm new password")
        self.reset_rate_limit()
        with patch("core.views.update_recovered_password", return_value=True) as update_provider:
            response = reset.post(
                "/password-reset/new/",
                {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD},
                follow=True,
            )
        update_provider.assert_called_once_with("encrypted-recovery-grant", NEW_PASSWORD)
        self.assertContains(response, "Your password has been reset")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))
        self.assertEqual(self.user.active_session_key, "")
        self.assertFalse(Session.objects.filter(session_key=previous_session_key).exists())
        self.assertTrue(AuditLog.objects.filter(action="client.password_reset", actor=self.user).exists())
        self.assertRedirects(
            signed_in.get("/dashboard/"),
            "/login/?next=%2Fdashboard%2F",
            fetch_redirect_response=False,
        )

        fresh = Browser()
        self.reset_rate_limit()
        self.assertRedirects(
            fresh.post("/login/", {"username": self.user.email, "password": NEW_PASSWORD}),
            "/dashboard/",
            fetch_redirect_response=False,
        )

    def test_reset_grant_expires_and_password_validation_is_enforced(self):
        browser = self.request_code()
        self.verify_code(browser)
        self.reset_rate_limit()
        weak = browser.post(
            "/password-reset/new/",
            {"new_password1": "short", "new_password2": "short"},
        )
        self.assertEqual(weak.status_code, 200)
        self.assertContains(weak, "at least 8 characters")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(OLD_PASSWORD))

        session = browser.session
        session["password_reset_verified_at"] = (timezone.now() - timedelta(minutes=11)).isoformat()
        session.save()
        expired = browser.get("/password-reset/new/", follow=True)
        self.assertContains(expired, "verified reset session expired")

    def test_provider_failure_does_not_change_local_password(self):
        browser = self.request_code()
        self.verify_code(browser)
        self.reset_rate_limit()
        with patch(
            "core.views.update_recovered_password",
            side_effect=VerificationServiceUnavailable("provider unavailable"),
        ):
            response = browser.post(
                "/password-reset/new/",
                {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD},
                follow=True,
            )
        self.assertContains(response, "Password recovery is temporarily unavailable")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(OLD_PASSWORD))
