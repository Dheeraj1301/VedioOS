import uuid
from io import StringIO
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import Client as Browser
from django.test import TestCase, override_settings
from django.utils import timezone

from core.identity_cleanup import (
    SupabaseDeletionSyncUnavailable,
    archive_deleted_identity,
    synchronize_supabase_deletions,
)
from core.models import Client, File, Order, Payment, Project, ProjectStorageCleanup, User
from core.payment_history import payment_page
from core.permissions import visible_projects
from operations.assignments import editor_roster
from operations.clients import client_roster
from operations.models import Admin, Editor, EditorAssignment
from operations.orders import order_page
from operations.projects import project_page

PASSWORD = "Synthetic-Cleanup-72!Leaf"


class SupabaseIdentityCleanupTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_user = User.objects.create_user(
            "cleanup-admin@example.test",
            PASSWORD,
            name="Cleanup Admin",
            role=User.Role.ADMIN,
            supabase_auth_user_id=uuid.uuid4(),
        )
        Admin.objects.create(user=cls.admin_user)

    def test_deleted_client_is_archived_out_of_admin_rosters(self):
        user = User.objects.create_user(
            "deleted-client@example.test",
            PASSWORD,
            name="Deleted Client",
            supabase_auth_user_id=uuid.uuid4(),
        )
        client = Client.objects.create(user=user)
        project = Project.objects.create(client=client, title="Archived project")
        order = Order.objects.create(project=project, total_minor=1000, currency="INR")
        payment = Payment.objects.create(
            order=order,
            provider="synthetic",
            provider_reference="deleted-client-payment",
            amount_minor=1000,
            currency="INR",
        )

        archive_deleted_identity(user.id)

        user.refresh_from_db()
        project.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertIsNotNone(user.auth_deleted_at)
        self.assertIsNotNone(project.archived_at)
        self.assertTrue(Project.objects.filter(pk=project.pk).exists())
        self.assertTrue(Order.objects.filter(pk=order.pk).exists())
        self.assertTrue(Payment.objects.filter(pk=payment.pk).exists())
        self.assertFalse(client_roster().filter(pk=client.pk).exists())
        self.assertFalse(visible_projects(self.admin_user).filter(pk=project.pk).exists())
        self.assertFalse(order_page()[0])
        self.assertFalse(payment_page(self.admin_user)[0])
        self.assertFalse(project_page(self.admin_user)[0])
        self.assertTrue(ProjectStorageCleanup.objects.filter(project=project).exists())

    def test_deleted_editor_is_unassigned_without_archiving_client_project(self):
        client_user = User.objects.create_user(
            "retained-client@example.test", PASSWORD, name="Retained Client"
        )
        client = Client.objects.create(user=client_user)
        project = Project.objects.create(
            client=client,
            title="Needs reassignment",
            status=Project.Status.EDITING,
        )
        editor_user = User.objects.create_user(
            "deleted-editor@example.test",
            PASSWORD,
            name="Deleted Editor",
            role=User.Role.EDITOR,
            supabase_auth_user_id=uuid.uuid4(),
        )
        editor = Editor.objects.create(
            user=editor_user,
            phone="00000",
            experience="Synthetic",
            tools="Synthetic",
            portfolio="https://example.test/editor",
            previous_work="Synthetic",
            expertise="Synthetic",
        )
        assignment = EditorAssignment.objects.create(
            project=project, editor=editor, assigned_by=self.admin_user
        )

        archive_deleted_identity(editor_user.id)

        assignment.refresh_from_db()
        project.refresh_from_db()
        self.assertIsNotNone(assignment.ended_at)
        self.assertEqual(project.status, Project.Status.WAITING)
        self.assertIsNone(project.archived_at)
        self.assertFalse(editor_roster().filter(pk=editor.pk).exists())
        self.assertTrue(visible_projects(self.admin_user).filter(pk=project.pk).exists())

    def test_last_active_admin_cannot_be_archived(self):
        with self.assertRaisesMessage(
            ValidationError, "The last active administrator cannot be deleted."
        ):
            archive_deleted_identity(self.admin_user.id)
        self.admin_user.refresh_from_db()
        self.assertTrue(self.admin_user.is_active)
        self.assertIsNone(self.admin_user.auth_deleted_at)

    @override_settings(
        SUPABASE_AUTH_URL="https://project.supabase.co",
        SUPABASE_SECRET_KEY="server-secret",
    )
    @patch("core.identity_cleanup.requests.get")
    def test_auth_inventory_reconciliation_archives_missing_identity(self, get):
        missing_auth_id = uuid.uuid4()
        user = User.objects.create_user(
            "missing-auth@example.test",
            PASSWORD,
            name="Missing Auth",
            supabase_auth_user_id=missing_auth_id,
        )
        Client.objects.create(user=user)
        get.return_value.status_code = 200
        get.return_value.json.return_value = {
            "users": [{"id": str(self.admin_user.supabase_auth_user_id)}]
        }

        result = synchronize_supabase_deletions()

        user.refresh_from_db()
        self.assertEqual(result, {"archived": 1, "blocked": 0})
        self.assertIsNotNone(user.auth_deleted_at)
        self.assertFalse(user.is_active)

    @override_settings(SUPABASE_DELETION_SYNC_ENABLED=True)
    @patch(
        "core.middleware.synchronize_supabase_deletions",
        side_effect=SupabaseDeletionSyncUnavailable("unavailable"),
    )
    def test_admin_roster_fails_closed_when_auth_cannot_be_verified(self, sync):
        browser = Browser()
        browser.force_login(self.admin_user)

        response = browser.get("/admin/clients/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response["Retry-After"], "30")
        self.assertContains(response, "temporarily unavailable", status_code=503)

    @patch("core.management.commands.cleanup_archived_project_storage.delete_private_object_versions")
    def test_storage_cleanup_removes_versions_then_closes_job(self, remove_versions):
        user = User.objects.create_user("storage-client@example.test", PASSWORD, name="Storage")
        client = Client.objects.create(user=user)
        project = Project.objects.create(client=client, title="Storage cleanup")
        file = File.objects.create(
            project=project,
            uploader=user,
            filename="source.mp4",
            object_key=f"projects/{project.pk}/source.mp4",
            storage_version="v1",
            content_type="video/mp4",
            size_bytes=4,
            sha256="0" * 64,
            category=File.Category.SOURCE,
            state="ready",
            expires_at=timezone.now(),
        )
        job = ProjectStorageCleanup.objects.create(project=project)

        output = StringIO()
        call_command("cleanup_archived_project_storage", stdout=output)

        remove_versions.assert_called_once_with(file.object_key)
        file.refresh_from_db()
        job.refresh_from_db()
        self.assertEqual(file.state, "removed")
        self.assertEqual(job.state, ProjectStorageCleanup.State.COMPLETED)
        self.assertEqual(job.object_count, 1)
        self.assertIn("completed=1", output.getvalue())
