import json
import uuid
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from core.delivery import transition
from core.earnings_reconciliation import earnings_reconciliation_report
from core.models import DeliveryAcceptance
from operations.earnings import decide_redemption, release_earning, request_redemption
from operations.models import CoinTransaction, EarningPolicy
from tests.assignment_fixtures import create_people, enable_test_policy
from tests.test_delivery import delivery_fixture, ready_output

RULE = {
    "version": "fixed_whole_v1",
    "coins": 120,
    "precision": "whole",
    "release_mode": "manual",
    "configured_at": "synthetic",
}


@override_settings(DEBUG=True, PAYOUT_MODE="sandbox")
class EarningsReconciliationTests(TestCase):
    def setUp(self):
        self.admin, self.buyer, self.editors = create_people()
        enable_test_policy()
        EarningPolicy.objects.filter(pk=1).update(
            enabled=True,
            rule="fixed_whole_v1",
            plan_1_coins=120,
            plan_2_coins=230,
            plan_3_coins=340,
            custom_coins=150,
            release_mode="manual",
            redemptions_enabled=True,
            redemption_minimum=20,
        )
        self.project = delivery_fixture(self.buyer, self.editors[0])
        self.project.order.terms_snapshot = {
            "review_rule": "latest_request_v1",
            "revision_limit": 1,
            "earning_rule": RULE,
        }
        self.project.order.save(update_fields=["terms_snapshot"])
        output = ready_output(self.project, self.editors[0].user)
        transition(self.editors[0].user, self.project.pk, "start")
        transition(self.editors[0].user, self.project.pk, "submit", file_id=output.pk)
        transition(
            self.buyer.user,
            self.project.pk,
            "accept",
            version_id=self.project.versions.get().pk,
        )
        self.acceptance = DeliveryAcceptance.objects.get(project=self.project)

    def test_pending_released_and_redemption_ledgers_reconcile(self):
        self.assertEqual(earnings_reconciliation_report()["status"], "pass")
        release_earning(self.admin, self.acceptance.pk)
        redemption = request_redemption(self.editors[0].user, 75, uuid.uuid4())
        decide_redemption(self.admin, redemption.pk, "paid", "synthetic-reference")
        report = earnings_reconciliation_report()
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["transaction_count"], 5)
        self.assertNotIn("synthetic-reference", json.dumps(report))

    def test_changed_acceptance_entry_is_detected(self):
        CoinTransaction.objects.filter(kind="pending").update(amount=121)
        report = earnings_reconciliation_report()
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["critical"]["acceptance_ledger_mismatch"], 1)

    def test_incomplete_paid_redemption_is_detected(self):
        release_earning(self.admin, self.acceptance.pk)
        redemption = request_redemption(self.editors[0].user, 75, uuid.uuid4())
        redemption.status = "paid"
        redemption.payout_reference = "synthetic-reference"
        redemption.decided_by = self.admin
        redemption.save(update_fields=["status", "payout_reference", "decided_by"])
        report = earnings_reconciliation_report()
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["critical"]["redemption_ledger_mismatch"], 1)
        self.assertEqual(report["critical"]["redemption_decision_mismatch"], 1)


class EarningsReconciliationCommandTests(TestCase):
    def test_command_fails_closed_with_aggregate_output(self):
        report = {
            "status": "fail",
            "code": "earnings_reconciliation_failed",
            "wallet_count": 1,
            "acceptance_count": 1,
            "transaction_count": 1,
            "redemption_count": 0,
            "critical": {"acceptance_ledger_mismatch": 1},
            "warnings": {},
            "critical_count": 1,
            "warning_count": 0,
        }
        output = StringIO()
        with patch(
            "core.management.commands.reconcile_earnings.earnings_reconciliation_report",
            return_value=report,
        ):
            with self.assertRaisesMessage(CommandError, "critical findings"):
                call_command("reconcile_earnings", stdout=output)
        self.assertNotIn("payout_reference", output.getvalue())
