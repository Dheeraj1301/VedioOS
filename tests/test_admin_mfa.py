import time
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import Client as Browser
from django.test import TestCase
from django.utils import timezone

from core.models import AdminMFA, User
from core.totp import STEP_SECONDS, code_at, matching_step
from operations.models import Admin, AuditLog

PASSWORD = "Synthetic-Admin-pass-123!"


def current_code(secret, offset=0):
    return code_at(secret, int(time.time() // STEP_SECONDS) + offset)


class TotpTests(TestCase):
    def test_rfc_6238_sha1_vector(self):
        secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # ASCII "12345678901234567890"
        self.assertEqual(code_at(secret, 59 // STEP_SECONDS), "287082")
        self.assertEqual(matching_step(secret, "287082", now=59), 1)
        self.assertIsNone(matching_step(secret, "287082", after_step=1, now=59))
        self.assertIsNone(matching_step(secret, "28708", now=59))


class AdminMfaTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("mfa-admin@example.test", PASSWORD, name="MFA Admin", role="admin")
        Admin.objects.create(user=self.admin)
        self.browser = Browser()

    def sign_in(self):
        return self.browser.post("/login/", {"username": self.admin.email, "password": PASSWORD})

    def test_first_sign_in_sets_up_authenticator_before_any_session(self):
        self.assertRedirects(self.sign_in(), "/login/verify/", fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.browser.session)
        self.assertEqual(self.browser.get("/admin/").status_code, 302)
        setup = self.browser.get("/login/verify/")
        self.assertContains(setup, "Setup key")
        secret = AdminMFA.objects.get(user=self.admin).secret

        wrong = self.browser.post("/login/verify/", {"code": "000000" if current_code(secret) != "000000" else "111111"})
        self.assertEqual(wrong.status_code, 400)
        self.assertNotIn("_auth_user_id", self.browser.session)

        done = self.browser.post("/login/verify/", {"code": current_code(secret)})
        self.assertRedirects(done, "/dashboard/", fetch_redirect_response=False)
        self.assertEqual(self.browser.get("/admin/").status_code, 200)
        self.assertIsNotNone(AdminMFA.objects.get(user=self.admin).confirmed_at)
        self.assertTrue(AuditLog.objects.filter(actor=self.admin, action="account.mfa_enabled").exists())

    def test_later_sign_in_hides_setup_key_and_rejects_reused_code(self):
        mfa = AdminMFA.objects.create(user=self.admin, secret="JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP", confirmed_at=timezone.now())
        code = current_code(mfa.secret)
        self.sign_in()
        self.assertNotContains(self.browser.get("/login/verify/"), "Setup key")
        self.assertEqual(self.browser.post("/login/verify/", {"code": code}).status_code, 302)

        second = Browser()
        second.post("/login/", {"username": self.admin.email, "password": PASSWORD})
        self.assertEqual(second.post("/login/verify/", {"code": code}).status_code, 400)

    def test_session_takeover_endpoint_cannot_skip_the_code(self):
        self.sign_in()
        self.browser.post("/login/session/", {"action": "replace"})
        self.assertNotIn("_auth_user_id", self.browser.session)
        self.assertEqual(self.browser.get("/admin/").status_code, 302)

    def test_code_step_expires_and_needs_a_password_first(self):
        self.assertRedirects(self.browser.get("/login/verify/"), "/login/", fetch_redirect_response=False)
        self.sign_in()
        session = self.browser.session
        session["mfa_pending_at"] = (timezone.now() - timedelta(minutes=11)).isoformat()
        session.save()
        self.assertRedirects(self.browser.post("/login/verify/", {"code": "123456"}), "/login/", fetch_redirect_response=False)

    def test_clients_are_not_asked_for_a_code(self):
        client = User.objects.create_user(
            "mfa-client@example.test", PASSWORD, name="Client", role="client", email_verified_at=timezone.now()
        )
        from core.models import Client

        Client.objects.create(user=client)
        response = Browser().post("/login/", {"username": client.email, "password": PASSWORD})
        self.assertRedirects(response, "/dashboard/", fetch_redirect_response=False)

    def test_reset_command_requires_setup_again(self):
        AdminMFA.objects.create(user=self.admin, secret="JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP", confirmed_at=timezone.now())
        call_command("reset_admin_mfa", email=self.admin.email, stdout=StringIO())
        self.assertFalse(AdminMFA.objects.filter(user=self.admin).exists())
        self.sign_in()
        self.assertContains(self.browser.get("/login/verify/"), "Setup key")
