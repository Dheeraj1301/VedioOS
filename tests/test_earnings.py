import uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings

from core.commerce import create_quote
from core.delivery import transition
from core.models import CommercePolicy, DeliveryAcceptance, Plan
from operations.earnings import (
    decide_redemption,
    quote_rule,
    release_earning,
    request_redemption,
    totals,
)
from operations.models import CoinTransaction, EarningPolicy, EditorCoins, RedemptionRequest
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
class EarningTests(TestCase):
    def setUp(self):
        self.admin, self.buyer, self.editors = create_people()
        enable_test_policy()
        self.policy = EarningPolicy.objects.get(pk=1)
        self.policy.enabled = True
        self.policy.rule = "fixed_whole_v1"
        self.policy.plan_1_coins = 120
        self.policy.plan_2_coins = 230
        self.policy.plan_3_coins = 340
        self.policy.custom_coins = 150
        self.policy.release_mode = "manual"
        self.policy.redemptions_enabled = True
        self.policy.redemption_minimum = 20
        self.policy.save()
        self.editor = self.editors[0].user
        self.project = delivery_fixture(self.buyer, self.editors[0])
        self.project.order.terms_snapshot = {
            "review_rule": "latest_request_v1",
            "revision_limit": 1,
            "earning_rule": RULE,
        }
        self.project.order.save()
        self.file = ready_output(self.project, self.editor)

    def accept(self):
        transition(self.editor, self.project.pk, "start")
        transition(self.editor, self.project.pk, "submit", file_id=self.file.pk)
        version = self.project.versions.get()
        transition(self.buyer.user, self.project.pk, "accept", version_id=version.pk)
        return DeliveryAcceptance.objects.get(project=self.project)

    def test_pending_to_earned_and_exactly_once(self):
        acceptance = self.accept()
        wallet = EditorCoins.objects.get(editor=self.editors[0])
        self.assertEqual(acceptance.earning_status, "pending_release")
        self.assertEqual(totals(wallet), {"pending": 120, "redeemable": 0, "redeemed": 0, "total_earned": 0})
        release_earning(self.admin, acceptance.pk)
        release_earning(self.admin, acceptance.pk)
        self.assertEqual(
            totals(wallet), {"pending": 0, "redeemable": 120, "redeemed": 0, "total_earned": 120}
        )
        self.assertEqual(CoinTransaction.objects.count(), 3)

    def test_unconfigured_old_agreement_never_invents_coins(self):
        self.project.order.terms_snapshot = {"review_rule": "latest_request_v1", "revision_limit": 1}
        self.project.order.save()
        acceptance = self.accept()
        self.assertEqual(acceptance.earning_status, "pending_policy")
        self.assertFalse(CoinTransaction.objects.exists())
        with self.assertRaises(ValidationError):
            release_earning(self.admin, acceptance.pk)

    def test_quote_snapshots_coin_amount_and_policy_changes_do_not_rewrite(self):
        self.assertEqual(quote_rule("custom", None, self.policy)["coins"], 150)
        plan = Plan.objects.create(
            slot=1,
            name="Test",
            price_minor=10000,
            currency="INR",
            features=["cuts"],
            revision_limit=1,
            delivery_hours=24,
            duration_limit_seconds=60,
            priority=1,
            active=True,
        )
        self.assertEqual(quote_rule("plan", plan, self.policy)["coins"], 120)
        policy = CommercePolicy.objects.create(
            currency="INR",
            terms="test",
            delivery_terms="test",
            refund_terms="test",
            tax_terms="test",
            quotes_enabled=True,
        )
        project = delivery_fixture(self.buyer, self.editors[1])
        project.status = "payment_pending"
        project.payment_completed_at = None
        project.save()
        project.order.payment_status = "pending"
        project.order.save()
        project.order.payments.all().delete()
        quote = create_quote(self.buyer.user, project.pk, "plan", plan.pk)
        self.assertEqual(quote.snapshot["earning_rule"]["coins"], 120)
        self.policy.plan_1_coins = 999
        self.policy.save()
        self.assertEqual(quote.snapshot["earning_rule"]["coins"], 120)
        self.assertTrue(policy.quotes_enabled)

    def test_reservation_retry_failure_and_success(self):
        self.accept()
        release_earning(self.admin, self.project.acceptance.pk)
        wallet = EditorCoins.objects.get(editor=self.editors[0])
        key = uuid.uuid4()
        first = request_redemption(self.editor, 75, key)
        self.assertEqual(request_redemption(self.editor, 75, key).pk, first.pk)
        self.assertEqual(totals(wallet)["redeemable"], 45)
        with self.assertRaises(ValidationError):
            request_redemption(self.editor, 75, uuid.uuid4())
        decide_redemption(self.admin, first.pk, "failed")
        decide_redemption(self.admin, first.pk, "failed")
        self.assertEqual(totals(wallet)["redeemable"], 120)
        second = request_redemption(self.editor, 75, uuid.uuid4())
        decide_redemption(self.admin, second.pk, "paid", "sandbox-reference-one")
        with self.assertRaises(ValidationError):
            decide_redemption(self.admin, second.pk, "paid", "different-reference")
        self.assertEqual(totals(wallet)["redeemed"], 75)
        self.assertEqual(totals(wallet)["redeemable"], 45)
        self.assertEqual(RedemptionRequest.objects.count(), 2)

    def test_rejection_release_and_conflicting_outcome(self):
        self.accept()
        release_earning(self.admin, self.project.acceptance.pk)
        request = request_redemption(self.editor, 30, uuid.uuid4())
        decide_redemption(self.admin, request.pk, "rejected")
        self.assertEqual(totals(request.wallet)["redeemable"], 120)
        with self.assertRaises(ValidationError):
            decide_redemption(self.admin, request.pk, "paid", "reused")

    @override_settings(PAYOUT_MODE="disabled")
    def test_real_payout_and_redemption_guard(self):
        self.accept()
        release_earning(self.admin, self.project.acceptance.pk)
        with self.assertRaises(ValidationError):
            request_redemption(self.editor, 30, uuid.uuid4())

    def test_permissions_and_immutable_entries(self):
        acceptance = self.accept()
        with self.assertRaises(PermissionDenied):
            release_earning(self.buyer.user, acceptance.pk)
        with self.assertRaises(PermissionDenied):
            request_redemption(self.buyer.user, 20, uuid.uuid4())
        entry = CoinTransaction.objects.get()
        entry.amount = 999
        with self.assertRaises(ValueError):
            entry.save()
        with self.assertRaises(ValueError):
            entry.delete()
        self.client.force_login(self.buyer.user)
        self.assertEqual(self.client.get("/editor/wallet/").status_code, 403)
        self.assertEqual(
            self.client.post(
                "/admin/payouts/action/", {"action": "release", "id": acceptance.pk}
            ).status_code,
            403,
        )

    def test_wallet_and_admin_pages(self):
        self.accept()
        self.client.force_login(self.editor)
        self.assertContains(self.client.get("/editor/wallet/"), "Pending release")
        self.client.force_login(self.admin)
        self.assertContains(self.client.get("/admin/payouts/"), "Release agreed coins")
        self.assertContains(self.client.get("/admin/earnings/"), "Earning settings")
