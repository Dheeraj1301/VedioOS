import hashlib
import hmac
import json
import time
import uuid

from django.test import TestCase, override_settings

from core.commerce import accept_quote, create_quote
from core.models import CommercePolicy, CustomService, Order, Plan, Project
from core.payments import apply_sandbox_event, start_checkout
from operations.assignments import assign_next, classify
from operations.models import EditorAssignment, RoundRobinState
from tests.assignment_fixtures import create_people, enable_test_policy

SECRET = "synthetic-assignment-payment-key-123456789"


@override_settings(DEBUG=True, PAYMENT_MODE="sandbox", SANDBOX_PAYMENT_SECRET=SECRET)
class PaidPlanAssignmentSimulationTests(TestCase):
    """Exercise real payment activation followed by the round-robin boundary."""

    @classmethod
    def setUpTestData(cls):
        cls.admin, cls.client_profile, cls.editors = create_people()
        enable_test_policy()
        CommercePolicy.objects.update_or_create(
            pk=1,
            defaults={
                "pricing_context": "production",
                "currency": "INR",
                "custom_base_minor": 10000,
                "custom_revision_limit": 2,
                "custom_delivery_hours": 24,
                "custom_duration_limit_seconds": 60,
                "custom_priority": 1,
                "terms": "Synthetic service terms",
                "delivery_terms": "Synthetic delivery terms",
                "refund_terms": "Synthetic refund terms",
                "tax_terms": "Synthetic tax terms",
                "quotes_enabled": True,
            },
        )
        cls.non_basic_plan = Plan.objects.create(
            slot=2,
            name="Synthetic Plan 2",
            price_minor=35000,
            currency="INR",
            features=["Synthetic non-basic feature"],
            revision_limit=3,
            delivery_hours=48,
            duration_limit_seconds=120,
            priority=2,
            active=True,
        )
        cls.custom_service = CustomService.objects.create(
            name="Synthetic custom service",
            price_minor=5000,
            currency="INR",
            active=True,
        )

    def confirm_payment(self, project, quote):
        accept_quote(self.client_profile.user, project.id, quote.id)
        payment = start_checkout(self.client_profile.user, project.id)
        event = {
            "event_id": uuid.uuid4().hex,
            "reference": payment.provider_reference,
            "order_id": str(payment.order_id),
            "amount_minor": payment.amount_minor,
            "currency": payment.currency,
            "status": "confirmed",
        }
        body = json.dumps(event).encode()
        stamp = str(int(time.time()))
        digest = hmac.new(SECRET.encode(), stamp.encode() + b"." + body, hashlib.sha256).hexdigest()
        apply_sandbox_event(body, f"{stamp}.{digest}")
        project.refresh_from_db()
        project.order.refresh_from_db()
        return payment

    def test_custom_then_non_basic_plan_payments_follow_round_robin(self):
        custom_project = Project.objects.create(
            client=self.client_profile,
            title="Synthetic custom paid assignment",
        )
        Order.objects.create(project=custom_project, kind="custom")
        custom_quote = create_quote(
            self.client_profile.user,
            custom_project.id,
            "custom",
            service_ids=[self.custom_service.id],
        )
        self.confirm_payment(custom_project, custom_quote)
        self.assertEqual(custom_project.status, "payment_completed")
        self.assertEqual(custom_project.order.payment_status, "confirmed")
        classify(self.admin, custom_project.id, "beginner", "Synthetic custom review", 0)
        custom_assignment = assign_next(custom_project.id)

        plan_project = Project.objects.create(
            client=self.client_profile,
            title="Synthetic Plan 2 paid assignment",
        )
        Order.objects.create(project=plan_project, kind="plan", plan=self.non_basic_plan)
        plan_quote = create_quote(
            self.client_profile.user,
            plan_project.id,
            "plan",
            plan_id=self.non_basic_plan.id,
        )
        self.confirm_payment(plan_project, plan_quote)
        self.assertEqual(plan_project.status, "payment_completed")
        self.assertEqual(plan_project.order.payment_status, "confirmed")
        classify(self.admin, plan_project.id, "beginner", "Synthetic Plan 2 review", 0)
        plan_assignment = assign_next(plan_project.id)

        self.assertEqual(custom_assignment.editor_id, self.editors[0].id)
        self.assertEqual(plan_assignment.editor_id, self.editors[1].id)
        self.assertEqual(EditorAssignment.objects.filter(ended_at__isnull=True).count(), 2)
        rotation = RoundRobinState.objects.get(proficiency_id="beginner")
        self.assertEqual(rotation.last_editor_id, self.editors[1].id)
        self.assertEqual(rotation.sequence, 2)

        custom_project.refresh_from_db()
        plan_project.refresh_from_db()
        self.assertEqual(custom_project.status, "editor_assigned")
        self.assertEqual(plan_project.status, "editor_assigned")
