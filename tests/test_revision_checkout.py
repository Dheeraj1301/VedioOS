import hashlib
import hmac
import uuid
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import (
    CommercePolicy,
    File,
    ProjectVersion,
    RevisionPlan,
    RevisionPlanPaymentEvent,
)
from core.revision_checkout import (
    confirm_revision_payment,
    create_revision_order,
    start_revision_checkout,
)
from operations.models import AuditLog, EditorAssignment
from tests.assignment_fixtures import create_people, enable_test_policy, paid_project


@override_settings(
    DEBUG=True,
    PAYMENT_MODE="razorpay_test",
    RAZORPAY_KEY_ID="rzp_test_synthetic",
    RAZORPAY_KEY_SECRET="synthetic-secret",
    RAZORPAY_API_BASE="https://api.razorpay.com/v1",
)
class RevisionCheckoutTests(TestCase):
    def setUp(self):
        self.admin, self.client_profile, self.editors = create_people()
        enable_test_policy()
        CommercePolicy.objects.create(pk=1, policy_version=4)
        self.project = paid_project(self.client_profile, "Ongoing edit")
        self.project.status = "awaiting_review"
        self.project.save(update_fields=["status", "updated_at"])
        self.project.order.terms_snapshot = {
            "review_rule": "latest_request_v1",
            "revision_limit": 0,
        }
        self.project.order.save(update_fields=["terms_snapshot", "updated_at"])
        self.assignment = EditorAssignment.objects.create(
            project=self.project,
            editor=self.editors[0],
        )
        draft = self._ready_file(self.editors[0].user, "draft.mp4", "draft")
        self.version = ProjectVersion.objects.create(
            project=self.project,
            file=draft,
            number=1,
            assignment=self.assignment,
        )
        self.plan1 = RevisionPlan.objects.create(
            slot=1,
            name="Punaha 1",
            price_minor=9900,
            currency="INR",
            description="One paid revision",
            active=True,
        )
        self.plan3 = RevisionPlan.objects.create(
            slot=3,
            name="Punaha 3",
            price_minor=49900,
            currency="INR",
            description="Revision with additional files",
            active=True,
        )

    def _ready_file(self, uploader, filename, category="asset"):
        return File.objects.create(
            project=self.project,
            uploader=uploader,
            filename=filename,
            object_key=f"synthetic/{uuid.uuid4()}",
            storage_version="verified-version",
            content_type="application/octet-stream",
            size_bytes=32,
            sha256="a" * 64,
            category=category,
            state="ready",
            expires_at=timezone.now(),
        )

    def _order(self, plan=None, files=None):
        return create_revision_order(
            self.client_profile.user,
            {
                "request_key": str(uuid.uuid4()),
                "plan_id": str((plan or self.plan1).pk),
                "project_id": str(self.project.pk),
                "song_reference": "https://example.test/new-song",
                "changes": "Tighten the opening and update the beat cuts.",
                "file_ids": [str(item.pk) for item in (files or [])],
            },
        )

    def test_revision_page_shows_conditional_form_and_only_ongoing_projects(self):
        completed = paid_project(self.client_profile, "Completed edit")
        completed.status = "completed"
        completed.save(update_fields=["status", "updated_at"])
        self.client.force_login(self.client_profile.user)

        response = self.client.get("/client/revisions/")

        self.assertContains(response, "Punaha 1")
        self.assertContains(response, "Select Project")
        self.assertContains(response, "Upload Additional Files")
        self.assertContains(response, "Ongoing edit")
        self.assertNotContains(response, "Completed edit")

    def test_punaha_three_saves_private_ready_attachments(self):
        attachment = self._ready_file(self.client_profile.user, "brief.pdf")

        order = self._order(self.plan3, [attachment])

        self.assertEqual(order.attachments.get().file, attachment)
        self.assertEqual(order.amount_minor, 49900)
        self.assertEqual(order.plan_snapshot["name"], "Punaha 3")

    @patch("core.revision_checkout._razorpay_request")
    def test_payment_uses_plan_price_and_forces_original_editor_when_unavailable(self, provider):
        self.editors[0].availability_override = "not_available"
        self.editors[0].availability_override_reason = "Synthetic unavailable state"
        self.editors[0].availability_override_by = self.admin
        self.editors[0].availability_override_at = timezone.now()
        self.editors[0].save()
        order = self._order()
        provider.return_value = {
            "id": "order_revision_synthetic",
            "amount": 9900,
            "currency": "INR",
            "status": "created",
        }
        payment = start_revision_checkout(self.client_profile.user, order.pk, "4")
        self.assertEqual(provider.call_args.kwargs["json"]["amount"], 9900)

        gateway_id = "pay_revision_synthetic"
        signature = hmac.new(
            b"synthetic-secret",
            f"{payment.provider_reference}|{gateway_id}".encode(),
            hashlib.sha256,
        ).hexdigest()
        provider.return_value = {
            "id": gateway_id,
            "order_id": payment.provider_reference,
            "amount": 9900,
            "currency": "INR",
            "status": "captured",
            "captured": True,
        }
        payload = {
            "razorpay_payment_id": gateway_id,
            "razorpay_order_id": payment.provider_reference,
            "razorpay_signature": signature,
        }

        event = confirm_revision_payment(self.client_profile.user, payment.pk, payload)
        duplicate = confirm_revision_payment(self.client_profile.user, payment.pk, payload)

        order.refresh_from_db()
        self.project.refresh_from_db()
        self.assertEqual(event.pk, duplicate.pk)
        self.assertEqual(RevisionPlanPaymentEvent.objects.count(), 1)
        self.assertEqual(order.revision_request.project_id, self.project.pk)
        self.assertEqual(order.revision_request.version_id, self.version.pk)
        self.assertEqual(self.project.status, "revision_requested")
        self.assertEqual(self.project.assignments.get(ended_at__isnull=True).editor_id, self.editors[0].pk)
        self.assertEqual(self.project.assignments.count(), 1)
        audit = AuditLog.objects.get(action="revision_plan_payment.confirmed")
        self.assertTrue(audit.detail["availability_bypassed"])
