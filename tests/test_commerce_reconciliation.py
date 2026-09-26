import hashlib
import json
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from core.commerce_reconciliation import commerce_reconciliation_report
from core.models import Client, Order, OrderQuote, Payment, PaymentEvent, Project, User
from operations.models import CallRequest


class CommerceReconciliationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "commerce-reconcile@example.test", "Synthetic-72!Leaf", name="Client"
        )
        self.project = Project.objects.create(
            client=Client.objects.create(user=self.user),
            title="Synthetic",
            call_before=True,
            payment_completed_at=timezone.now(),
            status="payment_completed",
        )
        self.order = Order.objects.create(
            project=self.project,
            kind="custom",
            total_minor=10000,
            currency="INR",
            payment_status="confirmed",
        )
        snapshot = {
            "version": 1,
            "kind": "custom",
            "items": [{"id": "base", "name": "Base", "amount_minor": 10000}],
            "terms": {"terms": "Synthetic"},
            "currency": "INR",
            "total_minor": 10000,
        }
        self.quote = OrderQuote.objects.create(
            order=self.order,
            snapshot=snapshot,
            total_minor=10000,
            currency="INR",
            accepted_at=timezone.now(),
        )
        self.order.terms_snapshot = {
            **snapshot,
            "quote_id": str(self.quote.pk),
            "accepted_at": self.quote.accepted_at.isoformat(),
        }
        self.order.save(update_fields=["terms_snapshot"])
        self.payment = Payment.objects.create(
            order=self.order,
            provider="synthetic",
            provider_reference="synthetic-reference",
            amount_minor=10000,
            currency="INR",
            status="confirmed",
            confirmed_at=timezone.now(),
        )
        PaymentEvent.objects.create(
            provider="synthetic",
            event_id="synthetic-event",
            payment=self.payment,
            payload_digest=hashlib.sha256(b"synthetic").hexdigest(),
            outcome="confirmed",
        )
        CallRequest.objects.create(
            project=self.project,
            requested_by=self.user,
            stage="before",
        )

    def test_consistent_paid_commerce_flow_passes(self):
        report = commerce_reconciliation_report()
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["critical_count"], 0)
        self.assertEqual(report["payment_count"], 1)

    def test_quote_payment_event_and_call_drift_are_aggregated(self):
        self.quote.snapshot = {"items": [{"amount_minor": -1}]}
        self.quote.save(update_fields=["snapshot"])
        self.payment.currency = "USD"
        self.payment.save(update_fields=["currency"])
        PaymentEvent.objects.filter(payment=self.payment).update(payload_digest="not-a-digest")
        CallRequest.objects.filter(project=self.project).update(requested_by=User.objects.create_user(
            "other-reconcile@example.test", "Synthetic-72!Leaf", name="Other"
        ))
        report = commerce_reconciliation_report()
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["critical"]["malformed_quote_snapshots"], 1)
        self.assertEqual(report["critical"]["payment_amount_or_currency_mismatch"], 1)
        self.assertEqual(report["critical"]["invalid_payment_events"], 1)
        self.assertEqual(report["critical"]["call_request_owner_mismatch"], 1)
        self.assertNotIn("synthetic-reference", json.dumps(report))

    def test_non_object_accepted_quote_is_reported_instead_of_crashing(self):
        self.quote.snapshot = []
        self.quote.save(update_fields=["snapshot"])
        report = commerce_reconciliation_report()
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["critical"]["malformed_quote_snapshots"], 1)
        self.assertEqual(report["critical"]["accepted_quote_order_mismatch"], 1)


class CommerceReconciliationCommandTests(TestCase):
    def test_command_fails_closed_with_aggregate_output(self):
        report = {
            "status": "fail",
            "code": "commerce_reconciliation_failed",
            "order_count": 1,
            "quote_count": 1,
            "payment_count": 1,
            "event_count": 0,
            "call_count": 0,
            "critical": {"confirmed_payments_missing_event": 1},
            "warnings": {},
            "critical_count": 1,
            "warning_count": 0,
        }
        output = StringIO()
        with patch(
            "core.management.commands.reconcile_commerce.commerce_reconciliation_report",
            return_value=report,
        ):
            with self.assertRaisesMessage(CommandError, "critical findings"):
                call_command("reconcile_commerce", stdout=output)
        self.assertNotIn("provider_reference", output.getvalue())
