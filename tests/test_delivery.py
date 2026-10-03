import base64
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.test import TestCase, override_settings
from django.utils import timezone

from core.delivery import transition
from core.models import DeliveryAcceptance, File, ProjectVersion
from operations.assignments import open_workload
from operations.models import AuditLog, CoinTransaction, EditorAssignment, Notification
from tests.assignment_fixtures import create_people, enable_test_policy, paid_project


def delivery_fixture(client, editor):
    project = paid_project(client)
    project.status = "editor_assigned"
    project.save()
    project.order.terms_snapshot = {"review_rule": "latest_request_v1", "revision_limit": 1}
    project.order.save()
    EditorAssignment.objects.create(project=project, editor=editor)
    return project


def ready_output(project, user):
    return File.objects.create(
        project=project,
        uploader=user,
        filename="synthetic.mp4",
        object_key=f"synthetic/{uuid.uuid4()}",
        storage_version="test-version",
        content_type="video/mp4",
        size_bytes=32,
        sha256="a" * 64,
        category="draft",
        state="ready",
        expires_at=timezone.now(),
    )


@override_settings(DEBUG=True)
class DeliveryTests(TestCase):
    def setUp(self):
        self.admin, self.buyer, self.editors = create_people()
        enable_test_policy()
        self.editor = self.editors[0].user
        self.project = delivery_fixture(self.buyer, self.editors[0])
        self.file = ready_output(self.project, self.editor)

    def submit(self, previous=None, final=False):
        transition(self.editor, self.project.pk, "start")
        transition(
            self.editor,
            self.project.pk,
            "submit",
            file_id=self.file.pk,
            version_id=previous.pk if previous else None,
            final=final,
        )
        return self.project.versions.latest("number")

    def test_revision_to_acceptance_and_duplicate_accept(self):
        first = self.submit()
        transition(self.buyer.user, self.project.pk, "revise", version_id=first.pk, note="00:03 trim")
        transition(self.buyer.user, self.project.pk, "revise", version_id=first.pk, note="00:03 trim")
        self.assertEqual(self.project.revisions.count(), 1)
        original = self.file.pk
        self.file = ready_output(self.project, self.editor)
        second = self.submit(first, final=True)
        for _ in range(2):
            transition(self.buyer.user, self.project.pk, "accept", version_id=second.pk)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, "completed")
        self.assertEqual(self.project.revisions.get().status, "addressed")
        self.assertEqual(DeliveryAcceptance.objects.count(), 1)
        self.assertEqual(CoinTransaction.objects.count(), 0)
        self.assertEqual(open_workload(self.editors[0]), 0)
        self.assertEqual(Notification.objects.count(), 7)
        self.assertEqual(ProjectVersion.objects.get(pk=first.pk).file_id, original)

    def test_accept_first_draft_without_duplicate_upload(self):
        version = self.submit()
        transition(self.buyer.user, self.project.pk, "accept", version_id=version.pk)
        self.assertEqual(self.project.versions.count(), 1)
        self.assertEqual(self.project.acceptance.version.file_id, self.file.pk)

    def test_final_flag_does_not_complete(self):
        self.submit(final=True)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, "awaiting_review")
        self.assertFalse(DeliveryAcceptance.objects.exists())

    def test_start_actions_are_attributable_and_retry_safe(self):
        transition(self.editor, self.project.pk, "start")
        transition(self.editor, self.project.pk, "start")
        started = AuditLog.objects.get(action="project.editing_started", target_id=str(self.project.pk))
        self.assertEqual(started.actor, self.editor)
        self.assertEqual(started.detail["assignment"], str(self.project.assignments.get().pk))
        self.assertEqual(started.detail["previous_status"], "editor_assigned")
        self.assertEqual(started.detail["status"], "editing")

        transition(
            self.editor,
            self.project.pk,
            "submit",
            file_id=self.file.pk,
        )
        version = self.project.versions.get()
        transition(self.buyer.user, self.project.pk, "revise", version_id=version.pk, note="Trim")
        transition(self.editor, self.project.pk, "start")
        transition(self.editor, self.project.pk, "start")
        revision_started = AuditLog.objects.get(
            action="project.revision_started", target_id=str(self.project.pk)
        )
        self.assertEqual(revision_started.actor, self.editor)
        self.assertEqual(revision_started.detail["previous_status"], "revision_requested")
        self.assertEqual(revision_started.detail["status"], "revision_in_progress")
        self.assertEqual(
            AuditLog.objects.filter(
                action__in=["project.editing_started", "project.revision_started"],
                target_id=str(self.project.pk),
            ).count(),
            2,
        )

    def test_limits_stale_acceptance_and_blank_revision(self):
        first = self.submit()
        with self.assertRaises(ValidationError):
            transition(self.buyer.user, self.project.pk, "revise", version_id=first.pk)
        transition(self.buyer.user, self.project.pk, "revise", version_id=first.pk, note="Trim")
        with self.assertRaises(ValidationError):
            transition(self.buyer.user, self.project.pk, "accept", version_id=first.pk)
        self.file = ready_output(self.project, self.editor)
        second = self.submit(first)
        with self.assertRaises(ValidationError):
            transition(self.buyer.user, self.project.pk, "accept", version_id=first.pk)
        with self.assertRaises(ValidationError):
            transition(self.buyer.user, self.project.pk, "revise", version_id=second.pk, note="More")

    def test_unconfigured_and_unpaid_blocked(self):
        order = self.project.order
        order.terms_snapshot = {}
        order.save()
        with self.assertRaises(ValidationError):
            transition(self.editor, self.project.pk, "start")
        order.payment_status = "pending"
        order.save()
        with self.assertRaises(Http404):
            transition(self.editor, self.project.pk, "start")

    def test_cross_role_and_unassigned_denied(self):
        with self.assertRaises(PermissionDenied):
            transition(self.buyer.user, self.project.pk, "start")
        with self.assertRaises(Http404):
            transition(self.editors[1].user, self.project.pk, "start")
        with self.assertRaises(PermissionDenied):
            transition(self.admin, self.project.pk, "start")

    @patch("core.views.download_permission", return_value="https://example.test/temporary")
    def test_unsubmitted_output_hidden_and_submitted_download_allowed(self, sign):
        self.client.force_login(self.buyer.user)
        path = f"/api/files/{self.file.pk}/download/"
        self.assertEqual(self.client.post(path).status_code, 404)
        self.assertEqual(self.client.get(f"/api/projects/{self.project.pk}/").json()["files"], [])
        sign.assert_not_called()
        self.submit()
        self.assertEqual(self.client.post(path).status_code, 200)
        self.client.logout()
        self.assertEqual(self.client.post(path).status_code, 401)

    @patch("core.views.inspect_object")
    def test_completed_editor_upload_is_immediately_versioned_for_client(self, inspect):
        transition(self.editor, self.project.pk, "start")
        pending = File.objects.create(
            project=self.project,
            uploader=self.editor,
            filename="client-cut.mov",
            object_key=f"synthetic/{uuid.uuid4()}",
            content_type="video/quicktime",
            size_bytes=32,
            sha256="b" * 64,
            category="draft",
            state="pending",
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        inspect.return_value = {
            "ContentLength": 32,
            "ContentType": "video/quicktime",
            "ChecksumSHA256": base64.b64encode(bytes.fromhex("b" * 64)).decode(),
            "VersionId": "stored-version",
        }

        self.client.force_login(self.editor)
        response = self.client.post(f"/api/files/{pending.pk}/complete/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["version"], 1)
        self.assertTrue(response.json()["available_to_client"])

        pending.refresh_from_db()
        version = pending.projectversion
        self.assertEqual(version.number, 1)
        self.assertEqual(version.assignment.editor.user, self.editor)
        self.assertEqual(self.project.versions.count(), 1)

        second = File.objects.create(
            project=self.project,
            uploader=self.editor,
            filename="final-cut.mkv",
            object_key=f"synthetic/{uuid.uuid4()}",
            content_type="video/x-matroska",
            size_bytes=32,
            sha256="d" * 64,
            category="final",
            state="pending",
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        inspect.return_value = {
            "ContentLength": 32,
            "ContentType": "video/x-matroska",
            "ChecksumSHA256": base64.b64encode(bytes.fromhex("d" * 64)).decode(),
            "VersionId": "stored-version-2",
        }
        response = self.client.post(f"/api/files/{second.pk}/complete/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["version"], 2)
        self.assertTrue(second.projectversion.is_final)

        self.client.force_login(self.buyer.user)
        page = self.client.get(f"/client/projects/{self.project.pk}/")
        self.assertContains(page, "client-cut.mov")
        self.assertContains(page, "Download version 1")
        self.assertContains(page, "final-cut.mkv")
        self.assertContains(page, "Download version 2")

        self.client.force_login(self.admin)
        files = self.client.get(f"/api/projects/{self.project.pk}/").json()["files"]
        self.assertTrue({"client-cut.mov", "final-cut.mkv"}.issubset(
            {item["filename"] for item in files}
        ))

    @patch("core.views.inspect_object")
    def test_failed_automatic_submission_does_not_create_ready_client_entry(self, inspect):
        pending = File.objects.create(
            project=self.project,
            uploader=self.editor,
            filename="too-early.mp4",
            object_key=f"synthetic/{uuid.uuid4()}",
            content_type="video/mp4",
            size_bytes=32,
            sha256="c" * 64,
            category="draft",
            state="pending",
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        inspect.return_value = {
            "ContentLength": 32,
            "ContentType": "video/mp4",
            "ChecksumSHA256": base64.b64encode(bytes.fromhex("c" * 64)).decode(),
            "VersionId": "stored-version",
        }

        self.client.force_login(self.editor)
        response = self.client.post(f"/api/files/{pending.pk}/complete/")
        self.assertEqual(response.status_code, 409)
        pending.refresh_from_db()
        self.assertEqual(pending.state, "pending")
        self.assertFalse(ProjectVersion.objects.filter(file=pending).exists())

        self.client.force_login(self.buyer.user)
        self.assertNotContains(
            self.client.get(f"/client/projects/{self.project.pk}/"), "too-early.mp4"
        )

    def test_submission_replay_and_unverified_file(self):
        version = self.submit()
        transition(self.editor, self.project.pk, "submit", file_id=self.file.pk)
        self.assertEqual(self.project.versions.count(), 1)
        with self.assertRaises(ValidationError):
            transition(self.editor, self.project.pk, "submit", file_id=self.file.pk, note="Changed")
        self.assertEqual(ProjectVersion.objects.get(pk=version.pk).note, "")

    def test_form_requires_acceptance_confirmation_and_handles_bad_uuid(self):
        version = self.submit()
        self.client.force_login(self.buyer.user)
        path = f"/orders/{self.project.pk}/delivery/"
        self.client.post(path, {"action": "accept", "version_id": version.pk})
        self.assertFalse(DeliveryAcceptance.objects.exists())
        self.client.force_login(self.editor)
        self.assertEqual(self.client.post(path, {"action": "submit", "file_id": "bad"}).status_code, 302)

    def test_project_page_renders_review_history(self):
        self.submit()
        self.client.force_login(self.buyer.user)
        response = self.client.get(f"/client/projects/{self.project.pk}/")
        self.assertContains(response, "Accept version 1")

    def test_cross_client_form_and_former_editor_files_denied(self):
        self.submit()
        _, other, _ = create_people()
        self.client.force_login(other.user)
        self.assertEqual(
            self.client.post(
                f"/orders/{self.project.pk}/delivery/", {"action": "accept", "confirm": "yes"}
            ).status_code,
            404,
        )
        self.project.assignments.update(ended_at=timezone.now())
        self.client.force_login(self.editor)
        self.assertEqual(self.client.post(f"/api/files/{self.file.pk}/download/").status_code, 404)
        self.assertNotContains(self.client.get("/orders/notifications/"), "Synthetic assignment")

    def test_pending_or_other_project_file_cannot_be_submitted(self):
        transition(self.editor, self.project.pk, "start")
        self.file.state = "pending"
        self.file.save()
        with self.assertRaises(ValidationError):
            transition(self.editor, self.project.pk, "submit", file_id=self.file.pk)
        other = delivery_fixture(self.buyer, self.editors[1])
        foreign_file = ready_output(other, self.editor)
        with self.assertRaises(ValidationError):
            transition(self.editor, self.project.pk, "submit", file_id=foreign_file.pk)
