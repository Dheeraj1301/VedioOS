import uuid
from unittest.mock import Mock, patch

import requests
from django.test import TestCase, override_settings

from core.models import Client, User
from operations.models import Admin, AuditLog

PASSWORD = "Supabase-Test-72!Leaf"


def response(status, body):
    result = Mock(status_code=status)
    result.json.return_value = body
    return result


@override_settings(
    SUPABASE_AUTH_URL="https://project.supabase.co",
    SUPABASE_AUTH_PUBLISHABLE_KEY="sb_publishable_test",
    SUPABASE_AUTH_TIMEOUT_SECONDS=7,
    SUPABASE_AUTH_PASSWORD_LOGIN_ENABLED=True,
)
class SupabasePasswordLoginTests(TestCase):
    @patch("core.supabase_auth.requests.get")
    @patch("core.supabase_auth.requests.post")
    def test_confirmed_auth_user_is_provisioned_as_shared_client(self, post, get):
        auth_id = uuid.uuid4()
        post.return_value = response(
            200,
            {
                "access_token": "temporary-access-token",
                "refresh_token": "temporary-refresh-token",
            },
        )
        get.return_value = response(
            200,
            {
                "id": str(auth_id),
                "email": "newauth@example.test",
                "email_confirmed_at": "2026-10-09T10:00:00Z",
                "user_metadata": {"role": "admin"},
            },
        )

        login = self.client.post(
            "/login/",
            {"username": "NEWAUTH@example.test", "password": PASSWORD},
        )

        self.assertRedirects(login, "/dashboard/", fetch_redirect_response=False)
        user = User.objects.get(email="newauth@example.test")
        self.assertEqual(user.role, User.Role.CLIENT)
        self.assertEqual(user.supabase_auth_user_id, auth_id)
        self.assertTrue(user.is_active)
        self.assertIsNotNone(user.email_verified_at)
        self.assertFalse(user.has_usable_password())
        self.assertTrue(Client.objects.filter(user=user).exists())
        self.assertEqual(self.client.get("/client/").status_code, 200)
        self.assertEqual(self.client.get("/admin/").status_code, 403)
        self.assertNotIn("temporary-access-token", str(dict(self.client.session)))
        self.assertTrue(
            AuditLog.objects.filter(
                actor=user,
                action="client.supabase_auth_provisioned",
                target_id=str(user.pk),
            ).exists()
        )
        self.assertEqual(post.call_count, 1)
        self.assertEqual(get.call_count, 1)

    @patch("core.supabase_auth.requests.get")
    @patch("core.supabase_auth.requests.post")
    def test_existing_client_is_linked_without_duplication(self, post, get):
        auth_id = uuid.uuid4()
        user = User.objects.create_user(
            "existing@example.test", "Different-Local-72!Leaf", name="Existing"
        )
        Client.objects.create(user=user)
        post.return_value = response(200, {"access_token": "short-lived"})
        get.return_value = response(
            200,
            {
                "id": str(auth_id),
                "email": user.email,
                "confirmed_at": "2026-10-09T10:00:00Z",
            },
        )

        login = self.client.post(
            "/login/", {"username": user.email, "password": PASSWORD}
        )

        self.assertRedirects(login, "/dashboard/", fetch_redirect_response=False)
        user.refresh_from_db()
        self.assertEqual(user.supabase_auth_user_id, auth_id)
        self.assertEqual(User.objects.filter(email=user.email).count(), 1)
        self.assertTrue(
            AuditLog.objects.filter(actor=user, action="client.supabase_auth_linked").exists()
        )

    @patch("core.supabase_auth.requests.post")
    def test_invalid_password_does_not_create_an_application_user(self, post):
        post.return_value = response(400, {"code": "invalid_credentials"})

        rejected = self.client.post(
            "/login/", {"username": "missing@example.test", "password": "wrong"}
        )

        self.assertEqual(rejected.status_code, 200)
        self.assertContains(rejected, "Supabase did not accept that email and password")
        self.assertFalse(User.objects.filter(email="missing@example.test").exists())
        self.assertFalse(self.client.session.get("_auth_user_id"))

    @patch("core.supabase_auth.requests.post")
    def test_supabase_identity_cannot_take_over_admin_email(self, post):
        admin = User.objects.create_user(
            "manager@example.test",
            "Admin-Local-72!Leaf",
            name="Manager",
            role=User.Role.ADMIN,
        )
        Admin.objects.create(user=admin)

        rejected = self.client.post(
            "/login/", {"username": admin.email, "password": PASSWORD}
        )

        self.assertEqual(rejected.status_code, 200)
        self.assertFalse(self.client.session.get("_auth_user_id"))
        admin.refresh_from_db()
        self.assertEqual(admin.role, User.Role.ADMIN)
        self.assertIsNone(admin.supabase_auth_user_id)
        post.assert_not_called()

    @patch("core.supabase_auth.requests.post", side_effect=requests.Timeout)
    def test_provider_outage_is_reported_without_creating_user(self, _post):
        unavailable = self.client.post(
            "/login/", {"username": "outage@example.test", "password": PASSWORD}
        )

        self.assertEqual(unavailable.status_code, 200)
        self.assertContains(unavailable, "Sign-in is temporarily unavailable")
        self.assertFalse(User.objects.filter(email="outage@example.test").exists())


@override_settings(
    SUPABASE_AUTH_URL="https://project.supabase.co",
    SUPABASE_AUTH_PUBLISHABLE_KEY="sb_publishable_test",
    SUPABASE_AUTH_TIMEOUT_SECONDS=7,
    SUPABASE_AUTH_PASSWORD_LOGIN_ENABLED=True,
)
class SupabaseEmailCodeLoginTests(TestCase):
    @patch("core.supabase_auth.requests.post")
    def test_send_code_uses_existing_identity_only(self, post):
        post.return_value = response(200, {})

        sent = self.client.post(
            "/login/code/",
            {"action": "send", "email": "EXISTING@example.test"},
        )

        self.assertRedirects(sent, "/login/code/", fetch_redirect_response=False)
        self.assertEqual(self.client.session["login_otp_email"], "existing@example.test")
        _, kwargs = post.call_args
        self.assertEqual(
            kwargs["json"],
            {"email": "existing@example.test", "create_user": False},
        )

    @patch("core.supabase_auth.requests.post")
    def test_valid_code_provisions_client_and_starts_django_session(self, post):
        auth_id = uuid.uuid4()
        post.return_value = response(
            200,
            {
                "access_token": "discard-this-token",
                "refresh_token": "discard-this-refresh-token",
                "user": {"id": str(auth_id), "email": "code@example.test"},
            },
        )
        session = self.client.session
        session["login_otp_email"] = "code@example.test"
        session.save()

        verified = self.client.post(
            "/login/code/",
            {"action": "verify", "code": "123456"},
        )

        self.assertRedirects(verified, "/client/", fetch_redirect_response=False)
        user = User.objects.get(email="code@example.test")
        self.assertEqual(user.role, User.Role.CLIENT)
        self.assertEqual(user.supabase_auth_user_id, auth_id)
        self.assertTrue(Client.objects.filter(user=user).exists())
        self.assertEqual(self.client.get("/client/").status_code, 200)
        self.assertEqual(self.client.get("/admin/").status_code, 403)
        self.assertNotIn("discard-this-token", str(dict(self.client.session)))
        _, kwargs = post.call_args
        self.assertEqual(
            kwargs["json"],
            {"email": "code@example.test", "token": "123456", "type": "email"},
        )

    @patch("core.supabase_auth.requests.post")
    def test_invalid_code_does_not_create_or_authenticate_user(self, post):
        post.return_value = response(403, {"code": "otp_expired"})
        session = self.client.session
        session["login_otp_email"] = "missing@example.test"
        session.save()

        rejected = self.client.post(
            "/login/code/",
            {"action": "verify", "code": "654321"},
        )

        self.assertEqual(rejected.status_code, 200)
        self.assertContains(rejected, "invalid or expired")
        self.assertFalse(User.objects.filter(email="missing@example.test").exists())
        self.assertFalse(self.client.session.get("_auth_user_id"))

    def test_password_login_page_links_to_email_code_flow(self):
        page = self.client.get("/login/")

        self.assertContains(page, 'href="/login/code/"')
