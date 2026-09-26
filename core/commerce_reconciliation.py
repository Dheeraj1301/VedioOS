"""Read-only quote, order, payment-event and paid-call reconciliation."""

import string

from django.db.models import Count, F, Q

from operations.models import CallRequest

from .models import Order, OrderQuote, Payment, PaymentEvent


def _valid_currency(value):
    return isinstance(value, str) and len(value) == 3 and value.isascii() and value.isupper()


def _quote_snapshot_findings():
    malformed = 0
    for quote in OrderQuote.objects.only("snapshot", "total_minor", "currency").iterator(
        chunk_size=100
    ):
        snapshot = quote.snapshot
        if not isinstance(snapshot, dict):
            malformed += 1
            continue
        items = snapshot.get("items")
        amounts = []
        if isinstance(items, list):
            for item in items:
                if (
                    not isinstance(item, dict)
                    or type(item.get("amount_minor")) is not int
                    or item["amount_minor"] <= 0
                ):
                    amounts = []
                    break
                amounts.append(item["amount_minor"])
        if (
            not amounts
            or sum(amounts) != quote.total_minor
            or snapshot.get("total_minor") != quote.total_minor
            or snapshot.get("currency") != quote.currency
            or not _valid_currency(quote.currency)
            or snapshot.get("kind") not in {"plan", "custom"}
            or not isinstance(snapshot.get("terms"), dict)
        ):
            malformed += 1
    return malformed


def _accepted_quote_findings():
    missing_or_mismatched = 0
    for quote in OrderQuote.objects.filter(accepted_at__isnull=False).select_related("order").iterator(
        chunk_size=100
    ):
        order = quote.order
        snapshot = order.terms_snapshot
        quote_snapshot = quote.snapshot
        if (
            not isinstance(snapshot, dict)
            or not isinstance(quote_snapshot, dict)
            or str(snapshot.get("quote_id", "")) != str(quote.pk)
            or snapshot.get("accepted_at") != quote.accepted_at.isoformat()
            or order.total_minor != quote.total_minor
            or order.currency != quote.currency
            or order.kind != quote_snapshot.get("kind")
            or snapshot.get("total_minor") != quote.total_minor
            or snapshot.get("currency") != quote.currency
        ):
            missing_or_mismatched += 1
    return missing_or_mismatched


def _payment_event_findings():
    invalid = 0
    hexdigits = set(string.hexdigits.lower())
    for event in PaymentEvent.objects.select_related("payment").iterator(chunk_size=100):
        digest = event.payload_digest.lower()
        if (
            event.provider != event.payment.provider
            or event.outcome not in {"confirmed", "failed"}
            or len(digest) != 64
            or any(character not in hexdigits for character in digest)
            or not event.event_id
        ):
            invalid += 1
    return invalid


def _missing_paid_calls():
    missing = 0
    paid_orders = Order.objects.filter(payment_status="confirmed").select_related("project")
    for order in paid_orders.iterator(chunk_size=100):
        expected = []
        if order.project.call_before:
            expected.append("before")
        if order.project.call_after:
            expected.append("after")
        existing = set(
            CallRequest.objects.filter(project=order.project).values_list("stage", flat=True)
        )
        missing += len(set(expected) - existing)
    return missing


def commerce_reconciliation_report():
    confirmed_payments = Payment.objects.filter(status="confirmed")
    failed_payments = Payment.objects.filter(status="failed")
    payment_counts = Order.objects.annotate(payment_count=Count("payments"))
    critical = {
        "malformed_quote_snapshots": _quote_snapshot_findings(),
        "accepted_quote_order_mismatch": _accepted_quote_findings(),
        "orders_with_snapshot_without_accepted_quote": Order.objects.exclude(terms_snapshot={})
        .exclude(quotes__accepted_at__isnull=False)
        .count(),
        "orders_with_multiple_payments": payment_counts.filter(payment_count__gt=1).count(),
        "payment_amount_or_currency_mismatch": Payment.objects.filter(
            Q(amount_minor__lte=0)
            | Q(order__total_minor__isnull=True)
            | Q(order__currency="")
            | ~Q(amount_minor=F("order__total_minor"))
            | ~Q(currency=F("order__currency"))
        ).count(),
        "confirmed_payment_state_mismatch": confirmed_payments.filter(
            Q(confirmed_at__isnull=True)
            | ~Q(order__payment_status="confirmed")
            | Q(order__project__payment_completed_at__isnull=True)
        ).count(),
        "failed_payment_state_mismatch": failed_payments.exclude(
            order__payment_status="failed"
        ).count(),
        "confirmed_payments_missing_event": confirmed_payments.exclude(
            events__outcome="confirmed"
        ).count(),
        "failed_payments_missing_event": failed_payments.exclude(events__outcome="failed").count(),
        "invalid_payment_events": _payment_event_findings(),
        "calls_on_unpaid_projects": CallRequest.objects.exclude(
            project__order__payment_status="confirmed"
        ).count(),
        "call_request_owner_mismatch": CallRequest.objects.exclude(
            requested_by_id=F("project__client__user_id")
        ).count(),
        "missing_paid_consultation_requests": _missing_paid_calls(),
    }
    warnings = {
        "accepted_unpaid_orders": Order.objects.filter(
            payment_status="pending", quotes__accepted_at__isnull=False
        ).count(),
        "failed_orders": Order.objects.filter(payment_status="failed").count(),
        "refunded_orders": Order.objects.filter(payment_status="refunded").count(),
    }
    critical_count = sum(critical.values())
    return {
        "status": "pass" if critical_count == 0 else "fail",
        "code": "commerce_consistent" if critical_count == 0 else "commerce_reconciliation_failed",
        "order_count": Order.objects.count(),
        "quote_count": OrderQuote.objects.count(),
        "payment_count": Payment.objects.count(),
        "event_count": PaymentEvent.objects.count(),
        "call_count": CallRequest.objects.count(),
        "critical": critical,
        "warnings": warnings,
        "critical_count": critical_count,
        "warning_count": sum(warnings.values()),
    }
