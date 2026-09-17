"""Append-only coin accounting. Whole coins have no monetary exchange rate here."""

import uuid

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from core.models import DeliveryAcceptance
from core.views import audit

from .models import CoinTransaction, EarningPolicy, EditorCoins, Notification, RedemptionRequest

MAX_COINS = 999999999999


def admin_only(user):
    if not user.is_authenticated or not user.is_active or user.role != "admin":
        raise PermissionDenied


def editor_only(user):
    if not user.is_authenticated or not user.is_active or user.role != "editor":
        raise PermissionDenied


def check_policy(policy):
    if not policy or not policy.enabled:
        return
    if policy.rule != "fixed_whole_v1" or policy.release_mode != "manual":
        raise ValidationError("Complete the earning policy before enabling it.")
    for name in ["plan_1_coins", "plan_2_coins", "plan_3_coins", "custom_coins"]:
        amount = getattr(policy, name)
        if type(amount) is not int or not 0 < amount <= MAX_COINS:
            raise ValidationError("Every plan and custom order needs a positive whole-coin amount.")
    if policy.redemptions_enabled and (
        not settings.DEBUG
        or getattr(settings, "PAYOUT_MODE", "disabled") != "sandbox"
        or not policy.redemption_minimum
        or policy.redemption_minimum > MAX_COINS
    ):
        raise ValidationError("Redemption requires an explicit development payout sandbox and minimum.")


def quote_rule(kind, plan, policy):
    if not policy or not policy.enabled:
        return None
    check_policy(policy)
    slot = plan.slot if kind == "plan" else None
    amount = getattr(policy, f"plan_{slot}_coins" if slot else "custom_coins")
    return {
        "version": "fixed_whole_v1",
        "coins": amount,
        "precision": "whole",
        "release_mode": "manual",
        "configured_at": policy.updated_at.isoformat(),
    }


def wallet_for(editor):
    wallet, _ = EditorCoins.objects.get_or_create(editor=editor)
    return wallet


def locked_earning_policy():
    return EarningPolicy.objects.select_for_update().get(pk=1)


def totals(wallet):
    values = dict(
        CoinTransaction.objects.filter(wallet=wallet)
        .values("kind")
        .annotate(total=Sum("amount"))
        .values_list("kind", "total")
    )
    pending = values.get("pending", 0)
    redeemable = sum(values.get(k, 0) for k in ["credit", "reserve", "release", "adjustment"])
    redeemed = values.get("redeem", 0)
    return {
        "pending": pending,
        "redeemable": redeemable,
        "redeemed": redeemed,
        "total_earned": values.get("credit", 0),
    }


def credit_acceptance(acceptance):
    """Called inside the locked delivery acceptance transaction."""
    rule = acceptance.terms_snapshot.get("earning_rule")
    if not isinstance(rule, dict) or rule.get("version") != "fixed_whole_v1":
        return
    amount = rule.get("coins")
    if type(amount) is not int or not 0 < amount <= MAX_COINS or rule.get("precision") != "whole":
        raise ValidationError("The order's saved earning rule is invalid. Contact the team.")
    wallet = wallet_for(acceptance.assignment.editor)
    _, created = CoinTransaction.objects.get_or_create(
        event_key=f"acceptance:{acceptance.pk}:pending",
        defaults={
            "wallet": wallet,
            "project": acceptance.project,
            "amount": amount,
            "kind": "pending",
            "rule_snapshot": rule,
        },
    )
    if created:
        acceptance.earning_status = "pending_release"
        acceptance.save(update_fields=["earning_status", "updated_at"])
        audit(acceptance.accepted_by, "coin.pending", acceptance.pk, {"coins": amount})


@transaction.atomic
def release_earning(admin, acceptance_id):
    admin_only(admin)
    locked_earning_policy()
    acceptance = (
        DeliveryAcceptance.objects.select_for_update()
        .select_related("assignment__editor", "project")
        .get(pk=acceptance_id)
    )
    if acceptance.earning_status == "earned":
        return acceptance
    if (
        acceptance.earning_status != "pending_release"
        or acceptance.project.status != "completed"
        or acceptance.project.order.payment_status != "confirmed"
    ):
        raise ValidationError("This acceptance has no releasable earning.")
    wallet = EditorCoins.objects.select_for_update().get(editor=acceptance.assignment.editor)
    entry = CoinTransaction.objects.get(event_key=f"acceptance:{acceptance.pk}:pending", wallet=wallet)
    rule = entry.rule_snapshot
    if rule.get("release_mode") != "manual" or entry.amount <= 0:
        raise ValidationError("Manual release is not covered by the saved agreement.")
    CoinTransaction.objects.create(
        wallet=wallet,
        project=acceptance.project,
        event_key=f"acceptance:{acceptance.pk}:pending_closed",
        amount=-entry.amount,
        kind="pending",
        rule_snapshot=rule,
    )
    CoinTransaction.objects.create(
        wallet=wallet,
        project=acceptance.project,
        event_key=f"acceptance:{acceptance.pk}:credit",
        amount=entry.amount,
        kind="credit",
        rule_snapshot=rule,
    )
    acceptance.earning_status = "earned"
    acceptance.save(update_fields=["earning_status", "updated_at"])
    Notification.objects.get_or_create(
        event_key=f"earning:{acceptance.pk}",
        defaults={
            "recipient": acceptance.assignment.editor.user,
            "project": acceptance.project,
            "message": "Approved coins are now available in your wallet.",
        },
    )
    audit(admin, "coin.released", acceptance.pk, {"coins": entry.amount})
    return acceptance


@transaction.atomic
def request_redemption(editor_user, amount, request_key):
    editor_only(editor_user)
    policy = locked_earning_policy()
    check_policy(policy)
    if not policy.enabled or not policy.redemptions_enabled:
        raise ValidationError("Redemption is not available.")
    if type(amount) is not int or amount < policy.redemption_minimum or amount > MAX_COINS:
        raise ValidationError("Enter a valid amount above the configured minimum.")
    try:
        request_key = uuid.UUID(str(request_key))
    except (ValueError, TypeError):
        raise ValidationError("Invalid request token. Reload the wallet and try again.") from None
    wallet = EditorCoins.objects.select_for_update().get(editor__user=editor_user)
    existing = RedemptionRequest.objects.filter(request_key=request_key).first()
    if existing:
        if existing.wallet_id == wallet.pk and existing.amount == amount:
            return existing
        raise ValidationError("This request token was already used.")
    if totals(wallet)["redeemable"] < amount:
        raise ValidationError("Insufficient redeemable coins.")
    redemption = RedemptionRequest.objects.create(
        wallet=wallet, amount=amount, status="requested", request_key=request_key
    )
    CoinTransaction.objects.create(
        wallet=wallet,
        redemption=redemption,
        event_key=f"redemption:{redemption.pk}:reserve",
        amount=-amount,
        kind="reserve",
        rule_snapshot={"minimum": policy.redemption_minimum, "mode": "sandbox"},
    )
    audit(editor_user, "redemption.requested", redemption.pk, {"coins": amount})
    return redemption


@transaction.atomic
def decide_redemption(admin, redemption_id, outcome, reference="", reason=""):
    admin_only(admin)
    locked_earning_policy()
    redemption = RedemptionRequest.objects.select_for_update().get(pk=redemption_id)
    wallet = EditorCoins.objects.select_for_update().get(pk=redemption.wallet_id)
    if redemption.status in {"paid", "failed", "rejected"}:
        if redemption.status == outcome:
            if outcome == "paid" and redemption.payout_reference != reference.strip():
                raise ValidationError("This payout has a different recorded reference.")
            return redemption
        raise ValidationError("This request already has a different final outcome.")
    if redemption.status != "requested" or outcome not in {"paid", "failed", "rejected"}:
        raise ValidationError("Invalid payout transition.")
    if outcome in {"paid", "failed"} and (
        not settings.DEBUG or getattr(settings, "PAYOUT_MODE", "disabled") != "sandbox"
    ):
        raise ValidationError(
            "A payout provider is not configured. Only the development sandbox can record this outcome."
        )
    if outcome == "paid" and (not reference.strip() or len(reference) > 200):
        raise ValidationError("A unique sandbox payout reference is required.")
    if outcome == "paid":
        CoinTransaction.objects.create(
            wallet=wallet,
            redemption=redemption,
            event_key=f"redemption:{redemption.pk}:redeem",
            amount=redemption.amount,
            kind="redeem",
            rule_snapshot={"mode": "sandbox", "reference": reference.strip()},
        )
    else:
        CoinTransaction.objects.create(
            wallet=wallet,
            redemption=redemption,
            event_key=f"redemption:{redemption.pk}:release",
            amount=redemption.amount,
            kind="release",
            rule_snapshot={"mode": "sandbox" if outcome == "failed" else "admin_rejection"},
        )
    redemption.status = outcome
    redemption.payout_reference = reference.strip() if outcome == "paid" else ""
    redemption.decided_by = admin
    redemption.decided_at = timezone.now()
    redemption.reason = reason.strip()[:500]
    redemption.save(
        update_fields=["status", "payout_reference", "decided_by", "decided_at", "reason", "updated_at"]
    )
    Notification.objects.get_or_create(
        event_key=f"redemption:{redemption.pk}:{outcome}",
        defaults={"recipient": wallet.editor.user, "message": f"Redemption request {outcome}."},
    )
    audit(admin, f"redemption.{outcome}", redemption.pk, {"coins": redemption.amount})
    return redemption
