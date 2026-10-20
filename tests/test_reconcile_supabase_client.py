import uuid
from io import StringIO
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from core.models import Client, User
from operations.models import AuditLog


def response(status, body):
    result = Mock(status_code=status)
    result.json.return_value = body
    return result


@override_settings(
    SUPABASE_AUTH_URL="https://project.supabase.co",
    SUPABASE_SECRET_KEY="server-secret",
    SUPABASE_AUTH_TIMEOUT_SECONDS=7,
)
class ReconcileSupabaseClientTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "client@example.test", "Local-Password-72!", name="Client"
        )
        Client.objects.create(user=self.user)

    @patch("core.management.commands.reconcile_supabase_client.requests.get")
    def test_links_unique_confirmed_identity_and_is_idempotent(self, get):
        auth_id = uuid.uuid4()
        get.return_value = response(
            200,
            {
                "users": [
                    {
                        "id": str(auth_id),
                        "email": "CLIENT@example.test",
                        "email_confirmed_at": "2026-10-20T10:00:00Z",
                    }
                ]
            },
        )

        output = StringIO()
        call_command("reconcile_supabase_client", email=self.user.email, stdout=output)
        call_command("reconcile_supabase_client", email=self.user.email, stdout=output)

        self.user.refresh_from_db()
        self.assertEqual(self.user.supabase_auth_user_id, auth_id)
        self.assertIsNotNone(self.user.email_verified_at)
        self.assertEqual(
            AuditLog.objects.filter(
                actor=self.user, action="client.supabase_auth_reconciled"
            ).count(),
            1,
        )
        self.assertIn("already reconciled", output.getvalue())

    @patch("core.management.commands.reconcile_supabase_client.requests.get")
    def test_refuses_to_replace_a_different_link(self, get):
        self.user.supabase_auth_user_id = uuid.uuid4()
        self.user.save(update_fields=["supabase_auth_user_id"])
        get.return_value = response(
            200,
            {
                "users": [
                    {
                        "id": str(uuid.uuid4()),
                        "email": self.user.email,
                        "confirmed_at": "2026-10-20T10:00:00Z",
                    }
                ]
            },
        )

        with self.assertRaisesRegex(CommandError, "refusing to overwrite"):
            call_command("reconcile_supabase_client", email=self.user.email)

    @patch("core.management.commands.reconcile_supabase_client.requests.get")
    def test_refuses_unconfirmed_identity(self, get):
        get.return_value = response(
            200,
            {"users": [{"id": str(uuid.uuid4()), "email": self.user.email}]},
        )

        with self.assertRaisesRegex(CommandError, "not confirmed"):
            call_command("reconcile_supabase_client", email=self.user.email)
