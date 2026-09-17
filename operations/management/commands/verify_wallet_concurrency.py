"""Verify PostgreSQL wallet locking without enabling the live policy."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections, connection, connections, transaction

from core.models import Client, User
from operations.earnings import locked_earning_policy, request_redemption, totals, wallet_for
from operations.models import (
    AuditLog,
    CoinTransaction,
    Editor,
    EditorAvailability,
    EditorCoins,
    RedemptionRequest,
)
from tests.assignment_fixtures import create_people


class Command(BaseCommand):
    help = "Race two synthetic redemptions against one wallet, then remove exact fixtures."

    def handle(self, **options):
        if connection.vendor != "postgresql" or not settings.DEBUG:
            raise CommandError("Requires development PostgreSQL.")
        admin, buyer, editors = create_people()
        editor = editors[0]
        wallet = wallet_for(editor)
        CoinTransaction.objects.create(
            wallet=wallet,
            event_key=f"synthetic:{uuid.uuid4()}",
            amount=120,
            kind="credit",
            rule_snapshot={"synthetic": True},
        )
        user_ids = [admin.pk, buyer.user_id] + [e.user_id for e in editors]
        original = locked_earning_policy

        def synthetic_policy():
            policy = original()  # Still takes the actual PostgreSQL row lock.
            policy.enabled = True
            policy.rule = "fixed_whole_v1"
            policy.release_mode = "manual"
            policy.plan_1_coins = 120
            policy.plan_2_coins = 230
            policy.plan_3_coins = 340
            policy.custom_coins = 150
            policy.redemptions_enabled = True
            policy.redemption_minimum = 20
            return policy

        barrier = Barrier(2)

        def worker():
            close_old_connections()
            try:
                barrier.wait(timeout=15)
                request_redemption(editor.user, 80, uuid.uuid4())
                return "reserved"
            except ValidationError:
                return "rejected"
            finally:
                connections["default"].close()

        try:
            with (
                patch("operations.earnings.locked_earning_policy", side_effect=synthetic_policy),
                patch.object(settings, "PAYOUT_MODE", "sandbox"),
            ):
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(lambda _: worker(), range(2)))
            if sorted(results) != ["rejected", "reserved"] or totals(wallet)["redeemable"] != 40:
                raise CommandError("Concurrent reservation exceeded the synthetic wallet balance.")
            self.stdout.write("PASS: two simultaneous 80-coin requests against 120 coins reserve only once.")
        finally:
            with transaction.atomic():
                CoinTransaction.objects.filter(wallet=wallet).delete()
                RedemptionRequest.objects.filter(wallet=wallet).delete()
                AuditLog.objects.filter(actor_id__in=user_ids).delete()
                EditorCoins.objects.filter(editor__in=editors).delete()
                EditorAvailability.objects.filter(editor__in=editors).delete()
                Editor.objects.filter(pk__in=[e.pk for e in editors]).delete()
                Client.objects.filter(pk=buyer.pk).delete()
                User.objects.filter(pk__in=user_ids).delete()
            self.stdout.write("PASS: exact synthetic fixtures removed; saved earning policy unchanged.")
