import uuid
from io import StringIO
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from core.models import User
from operations.models import Admin, AuditLog

PASSWORD = "Provision-72!Leaf"


@override_settings(
    SUPABASE_AUTH_URL="https://project.supabase.co",
    SUPABASE_SECRET_KEY="sb_secret_test",
)
class SupabaseAdminProvisioningTests(TestCase):
    @patch("core.management.commands.create_supabase_admin.getpass", return_value=PASSWORD)
    @patch("core.management.commands.create_supabase_admin.requests.post")
    def test_creates_confirmed_auth_link_and_private_admin(self, post, getpass):
        auth_id = uuid.uuid4()
        post.return_value = Mock(status_code=201)
        post.return_value.json.return_value = {"id": str(auth_id)}

        output = StringIO()
        call_command(
            "create_supabase_admin",
            email="NEW-ADMIN@example.test",
            name="New Admin",
            stdout=output,
        )

        user = User.objects.get(email="new-admin@example.test")
        self.assertEqual(user.role, User.Role.ADMIN)
        self.assertEqual(user.supabase_auth_user_id, auth_id)
        self.assertIsNotNone(user.email_verified_at)
        self.assertTrue(user.check_password(PASSWORD))
        self.assertTrue(Admin.objects.filter(user=user).exists())
        self.assertTrue(
            AuditLog.objects.filter(actor=user, action="admin.provisioned").exists()
        )
        request_body = post.call_args.kwargs["json"]
        self.assertIs(request_body["email_confirm"], True)
        self.assertNotIn("role", request_body["user_metadata"])
        self.assertIn("linked admin created", output.getvalue())

