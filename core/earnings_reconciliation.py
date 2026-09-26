"""Read-only acceptance, coin-ledger and redemption reconciliation."""

from core.models import DeliveryAcceptance
from operations.models import CoinTransaction, EditorCoins, RedemptionRequest

EARNING_STATUSES = {"pending_policy", "pending_release", "earned"}
REDEMPTION_STATUSES = {"requested", "paid", "failed", "rejected"}
TRANSACTION_KINDS = {"pending", "credit", "reserve", "redeem", "release", "adjustment"}


def _earning_rule(acceptance):
    terms = acceptance.terms_snapshot
    rule = terms.get("earning_rule") if isinstance(terms, dict) else None
    if rule is None:
        return None
    if (
        not isinstance(rule, dict)
        or rule.get("version") != "fixed_whole_v1"
        or type(rule.get("coins")) is not int
        or rule["coins"] <= 0
        or rule.get("precision") != "whole"
        or rule.get("release_mode") != "manual"
    ):
        return False
    return rule


def _matches(entry, *, wallet_id, project_id, amount, kind, rule):
    return bool(
        entry
        and entry.wallet_id == wallet_id
        and entry.project_id == project_id
        and entry.redemption_id is None
        and entry.amount == amount
        and entry.kind == kind
        and entry.rule_snapshot == rule
    )


def _acceptance_findings():
    invalid_status = 0
    invalid_rule = 0
    ledger_mismatch = 0
    rows = DeliveryAcceptance.objects.select_related("assignment__editor__wallet", "project__order")
    for acceptance in rows.iterator(chunk_size=100):
        status = acceptance.earning_status
        if status not in EARNING_STATUSES:
            invalid_status += 1
            continue
        rule = _earning_rule(acceptance)
        prefix = f"acceptance:{acceptance.pk}:"
        entries = {
            entry.event_key: entry
            for entry in CoinTransaction.objects.filter(event_key__startswith=prefix)
        }
        if status == "pending_policy":
            if rule is False:
                invalid_rule += 1
            if rule is not None or entries:
                ledger_mismatch += 1
            continue
        if not rule:
            invalid_rule += 1
            continue
        try:
            wallet_id = acceptance.assignment.editor.wallet.pk
        except EditorCoins.DoesNotExist:
            ledger_mismatch += 1
            continue
        amount = rule["coins"]
        pending = entries.get(f"{prefix}pending")
        pending_ok = _matches(
            pending,
            wallet_id=wallet_id,
            project_id=acceptance.project_id,
            amount=amount,
            kind="pending",
            rule=rule,
        )
        if status == "pending_release":
            if not pending_ok or len(entries) != 1:
                ledger_mismatch += 1
            continue
        closed = entries.get(f"{prefix}pending_closed")
        credit = entries.get(f"{prefix}credit")
        if (
            not pending_ok
            or not _matches(
                closed,
                wallet_id=wallet_id,
                project_id=acceptance.project_id,
                amount=-amount,
                kind="pending",
                rule=rule,
            )
            or not _matches(
                credit,
                wallet_id=wallet_id,
                project_id=acceptance.project_id,
                amount=amount,
                kind="credit",
                rule=rule,
            )
            or len(entries) != 3
        ):
            ledger_mismatch += 1
    return invalid_status, invalid_rule, ledger_mismatch


def _transaction_shape_findings():
    invalid = 0
    for entry in CoinTransaction.objects.select_related("redemption").iterator(chunk_size=100):
        if (
            entry.kind not in TRANSACTION_KINDS
            or entry.amount == 0
            or not isinstance(entry.rule_snapshot, dict)
            or not entry.event_key
        ):
            invalid += 1
            continue
        if entry.redemption_id:
            if (
                entry.wallet_id != entry.redemption.wallet_id
                or entry.project_id is not None
                or entry.kind not in {"reserve", "redeem", "release"}
            ):
                invalid += 1
        elif entry.event_key.startswith("acceptance:"):
            if entry.project_id is None or entry.kind not in {"pending", "credit"}:
                invalid += 1
        elif entry.kind != "adjustment":
            invalid += 1
        if (
            (entry.kind == "reserve" and entry.amount >= 0)
            or (entry.kind in {"credit", "redeem", "release"} and entry.amount <= 0)
        ):
            invalid += 1
    return invalid


def _redemption_findings():
    invalid_status = 0
    ledger_mismatch = 0
    decision_mismatch = 0
    for redemption in RedemptionRequest.objects.select_related("decided_by").iterator(chunk_size=100):
        status = redemption.status
        if status not in REDEMPTION_STATUSES:
            invalid_status += 1
            continue
        entries = {
            entry.event_key: entry
            for entry in CoinTransaction.objects.filter(redemption=redemption)
        }
        prefix = f"redemption:{redemption.pk}:"
        reserve = entries.get(f"{prefix}reserve")
        reserve_ok = bool(
            reserve
            and reserve.wallet_id == redemption.wallet_id
            and reserve.project_id is None
            and reserve.amount == -redemption.amount
            and reserve.kind == "reserve"
        )
        if status == "requested":
            if not reserve_ok or len(entries) != 1:
                ledger_mismatch += 1
            if redemption.decided_by_id or redemption.decided_at or redemption.payout_reference:
                decision_mismatch += 1
            continue
        if (
            not redemption.decided_by_id
            or not redemption.decided_at
            or redemption.decided_by.role != "admin"
        ):
            decision_mismatch += 1
        outcome_kind = "redeem" if status == "paid" else "release"
        outcome = entries.get(f"{prefix}{outcome_kind}")
        if (
            not reserve_ok
            or not outcome
            or outcome.wallet_id != redemption.wallet_id
            or outcome.project_id is not None
            or outcome.amount != redemption.amount
            or outcome.kind != outcome_kind
            or len(entries) != 2
        ):
            ledger_mismatch += 1
        if (status == "paid" and not redemption.payout_reference) or (
            status != "paid" and redemption.payout_reference
        ):
            decision_mismatch += 1
    return invalid_status, ledger_mismatch, decision_mismatch


def _wallet_balance_findings():
    negative_pending = 0
    negative_redeemable = 0
    for wallet in EditorCoins.objects.iterator(chunk_size=100):
        entries = CoinTransaction.objects.filter(wallet=wallet).values_list("kind", "amount")
        pending = 0
        redeemable = 0
        for kind, amount in entries:
            if kind == "pending":
                pending += amount
            if kind in {"credit", "reserve", "release", "adjustment"}:
                redeemable += amount
        negative_pending += pending < 0
        negative_redeemable += redeemable < 0
    return negative_pending, negative_redeemable


def earnings_reconciliation_report():
    acceptance_status, acceptance_rule, acceptance_ledger = _acceptance_findings()
    redemption_status, redemption_ledger, redemption_decision = _redemption_findings()
    negative_pending, negative_redeemable = _wallet_balance_findings()
    critical = {
        "invalid_acceptance_status": acceptance_status,
        "invalid_acceptance_earning_rule": acceptance_rule,
        "acceptance_ledger_mismatch": acceptance_ledger,
        "invalid_transaction_shape": _transaction_shape_findings(),
        "invalid_redemption_status": redemption_status,
        "redemption_ledger_mismatch": redemption_ledger,
        "redemption_decision_mismatch": redemption_decision,
        "negative_pending_wallets": negative_pending,
        "negative_redeemable_wallets": negative_redeemable,
    }
    warnings = {
        "acceptances_awaiting_policy": DeliveryAcceptance.objects.filter(
            earning_status="pending_policy"
        ).count(),
        "redemptions_awaiting_decision": RedemptionRequest.objects.filter(
            status="requested"
        ).count(),
        "failed_or_rejected_redemptions": RedemptionRequest.objects.filter(
            status__in=["failed", "rejected"]
        ).count(),
        "earned_refunded_acceptances": DeliveryAcceptance.objects.filter(
            earning_status="earned", project__order__payment_status="refunded"
        ).count(),
    }
    critical_count = sum(critical.values())
    return {
        "status": "pass" if critical_count == 0 else "fail",
        "code": "earnings_consistent" if critical_count == 0 else "earnings_reconciliation_failed",
        "wallet_count": EditorCoins.objects.count(),
        "acceptance_count": DeliveryAcceptance.objects.count(),
        "transaction_count": CoinTransaction.objects.count(),
        "redemption_count": RedemptionRequest.objects.count(),
        "critical": critical,
        "warnings": warnings,
        "critical_count": critical_count,
        "warning_count": sum(warnings.values()),
    }
