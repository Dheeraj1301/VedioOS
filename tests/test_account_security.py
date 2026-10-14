from unittest.mock import patch

from django.test import Client as Browser
from django.test import TestCase

from core.email_verification import VerificationCooldown, VerificationServiceUnavailable
from core.models import Client, User

PASSWORD = "Strong-Test-42!"


class AccountSecurityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "secure@example.test",
            PASSWORD,
            name="Secure Client",
            role="client",
            is_active=True,
        )
        Client.objects.create(user=self.user)

    def test_verification_page_has_clear_code_and_resend_controls(self):
        browser = Browser()
        session = browser.session
        session["verification_email"] = "new@example.test"
        session.save()

        response = browser.get("/verify-email/")

        self.assertContains(response, "Check your email")
        self.assertContains(response, "six-digit code")
        self.assertContains(response, "The code expires after 10 minutes")
        self.assertContains(response, "Send a new code")
        self.assertContains(response, 'autocomplete="one-time-code"', html=False)

    def test_known_account_resend_reports_cooldown_and_outage(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        for exception, message in [
            (VerificationCooldown(), "A code was requested recently"),
            (VerificationServiceUnavailable(), "We could not send a new code right now"),
        ]:
            browser = Browser()
            session = browser.session
            session["verification_email"] = self.user.email
            session.save()
            with (
                self.subTest(exception=type(exception).__name__),
                patch("core.views.send_verification_email", side_effect=exception),
            ):
                response = browser.post("/verify-email/resend/", {"email": self.user.email}, follow=True)
                self.assertContains(response, message)

    def test_second_device_can_cancel_or_replace_the_active_session(self):
        first = Browser()
        second = Browser()
        self.assertRedirects(
            first.post("/login/", {"username": self.user.email, "password": PASSWORD}),
            "/dashboard/",
            fetch_redirect_response=False,
        )

        conflict = second.post("/login/", {"username": self.user.email, "password": PASSWORD})
        self.assertEqual(conflict.status_code, 409)
        self.assertContains(conflict, "This account is already signed in", status_code=409)
        self.assertContains(conflict, "Keep other device", status_code=409)
        self.assertContains(conflict, "Sign out other device", status_code=409)
        self.assertFalse(second.session.get("_auth_user_id"))

        self.assertRedirects(
            second.post("/login/session/", {"action": "keep"}),
            "/login/",
        )
        self.assertEqual(first.get("/client/").status_code, 200)

        second.post("/login/", {"username": self.user.email, "password": PASSWORD})
        self.assertRedirects(
            second.post("/login/session/", {"action": "replace"}),
            "/dashboard/",
            fetch_redirect_response=False,
        )
        ended = first.get("/client/", follow=True)
        self.assertRedirects(ended, "/login/?session=ended")
        self.assertContains(ended, "signed out because this account was used")
        self.assertEqual(second.get("/client/").status_code, 200)

    def test_session_replacement_requires_recent_authenticated_login(self):
        response = Browser().post("/login/session/", {"action": "replace"})
        self.assertRedirects(response, "/login/")
