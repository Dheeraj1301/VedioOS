from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import Client, File, Project, ProjectStorageCleanup, User
from operations.models import Admin, AuditLog
from operations.storage_costs import storage_cost_report

PASSWORD = "Synthetic-Cost-pass-123!"


class StorageCostTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("cost-admin@example.test", PASSWORD, name="Cost Admin", role="admin")
        Admin.objects.create(user=self.admin)
        owner = User.objects.create_user("cost-client@example.test", PASSWORD, name="Cost Client")
        self.client_profile = Client.objects.create(user=owner)
        self.owner = owner
        self.client.force_login(self.admin)

    def make_project(self, status, size_gb=1, days_stored=30):
        project = Project.objects.create(client=self.client_profile, title=f"{status} project", status=status)
        stored_since = timezone.now() - timedelta(days=days_stored)
        file = File.objects.create(
            project=project, uploader=self.owner, filename="source.mp4", object_key=f"edits/projects/{project.pk}/f",
            storage_version="v1", content_type="video/mp4", size_bytes=size_gb * 10**9, sha256="0" * 64,
            category=File.Category.SOURCE, state="ready", expires_at=timezone.now(), completed_at=stored_since,
        )
        return project, file

    @override_settings(AWS_S3_STORAGE_USD_PER_GB_MONTH=Decimal("0.025"), AWS_S3_EGRESS_USD_PER_GB=Decimal("0.114"),
                       AWS_S3_PUT_USD_PER_1000=Decimal("0"), AWS_S3_GET_USD_PER_1000=Decimal("0"),
                       AWS_CREDITS_USD=Decimal("100"))
    def test_cost_counts_storage_time_and_authorised_downloads(self):
        project, file = self.make_project(Project.Status.EDITING, size_gb=1, days_stored=30)
        AuditLog.objects.create(actor=self.owner, action="file.download_authorized", target_id=str(file.pk))
        AuditLog.objects.create(actor=self.owner, action="file.download_authorized", target_id=str(file.pk))
        report = storage_cost_report()
        row = next(r for r in report["rows"] if r["project"].pk == project.pk)
        self.assertAlmostEqual(float(row["storage_usd"]), 0.025, places=3)  # 1 GB for 30 days
        self.assertAlmostEqual(float(row["egress_usd"]), 0.228, places=3)  # 2 downloads of 1 GB
        self.assertEqual(row["downloads"], 2)
        self.assertFalse(row["deletable"])
        self.assertEqual(report["credits_left"], (Decimal("100") - report["totals"]["total"]).quantize(Decimal("0.01")))

    def test_dashboard_is_admin_only(self):
        self.assertEqual(self.client.get("/admin/storage-costs/").status_code, 200)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get("/admin/storage-costs/").status_code, 403)

    @patch("core.project_storage.delete_private_object_versions")
    def test_admin_deletes_completed_project_files_with_confirmation(self, remove_versions):
        project, file = self.make_project(Project.Status.COMPLETED)
        url = f"/admin/storage-costs/projects/{project.pk}/delete/"
        self.client.post(url, {})
        project.refresh_from_db()
        self.assertIsNone(project.archived_at)
        remove_versions.assert_not_called()

        self.client.post(url, {"confirm": "yes"})
        project.refresh_from_db()
        file.refresh_from_db()
        self.assertIsNotNone(project.archived_at)
        remove_versions.assert_called_once_with(file.object_key)
        self.assertEqual(file.state, "removed")
        self.assertEqual(ProjectStorageCleanup.objects.get(project=project).state, "completed")
        self.assertTrue(AuditLog.objects.filter(actor=self.admin, action="project.storage_deleted").exists())

    @patch("core.project_storage.delete_private_object_versions")
    def test_projects_in_progress_cannot_be_deleted(self, remove_versions):
        project, _file = self.make_project(Project.Status.EDITING)
        self.client.post(f"/admin/storage-costs/projects/{project.pk}/delete/", {"confirm": "yes"})
        project.refresh_from_db()
        self.assertIsNone(project.archived_at)
        remove_versions.assert_not_called()

    @patch("core.project_storage.delete_private_object_versions", side_effect=OSError("offline"))
    def test_unreachable_storage_queues_a_retry(self, _remove_versions):
        project, file = self.make_project(Project.Status.COMPLETED)
        self.client.post(f"/admin/storage-costs/projects/{project.pk}/delete/", {"confirm": "yes"})
        file.refresh_from_db()
        self.assertEqual(ProjectStorageCleanup.objects.get(project=project).state, "retry")
        self.assertEqual(file.state, "ready")
