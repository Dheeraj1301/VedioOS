from unittest.mock import patch

from django.test import Client as Browser
from django.test import TestCase
from django.utils import timezone

from core.email_verification import VerificationCooldown, VerificationServiceUnavailable
from core.models import Client, User
from core.sessions import PENDING_LOGIN_AT, PENDING_LOGIN_DESTINATION, PENDING_LOGIN_USER

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

    def test_stale_session_choice_reloads_fresh_form_without_raw_csrf_page(self):
        browser = Browser(enforce_csrf_checks=True)
        session = browser.session
        session[PENDING_LOGIN_USER] = str(self.user.pk)
        session[PENDING_LOGIN_DESTINATION] = "dashboard"
        session[PENDING_LOGIN_AT] = timezone.now().isoformat()
        session.save()

        stale = browser.post(
            "/login/session/",
            {"action": "keep", "csrfmiddlewaretoken": "incorrect"},
        )
        self.assertEqual(stale.status_code, 409)
        refreshed = stale
        self.assertContains(refreshed, "This account is already signed in", status_code=409)
        self.assertNotContains(refreshed, "Only one device can use", status_code=409)
        self.assertNotContains(
            refreshed,
            "This login attempt will be cancelled",
            status_code=409,
        )
        self.assertContains(refreshed, "Keep other device", status_code=409)
        self.assertContains(refreshed, "Sign out other device", status_code=409)

        token = browser.cookies["csrftoken"].value
        accepted = browser.post(
            "/login/session/",
            {"action": "keep", "csrfmiddlewaretoken": token},
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertRedirects(accepted, "/login/")

    def test_stale_sign_in_forms_reload_instead_of_showing_django_csrf_help(self):
        for path in ["/login/", "/editor/signin/"]:
            with self.subTest(path=path):
                browser = Browser(enforce_csrf_checks=True)
                browser.get(path)
                stale = browser.post(
                    path,
                    {
                        "username": "unused@example.test",
                        "password": "unused-password",
                        "csrfmiddlewaretoken": "incorrect",
                    },
                )
                self.assertRedirects(stale, path)
                refreshed = browser.get(path)
                self.assertContains(refreshed, "csrfmiddlewaretoken")
                self.assertNotContains(refreshed, "CSRF verification failed")

    def test_other_stale_protected_forms_use_safe_application_error(self):
        browser = Browser(enforce_csrf_checks=True)
        browser.force_login(self.user)

        response = browser.post("/logout/")

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "This form is no longer current.", status_code=403)
        self.assertNotContains(response, "CSRF verification failed", status_code=403)
