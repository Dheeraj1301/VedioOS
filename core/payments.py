"""Payment boundary. Only a signed development gateway is implemented so far.

Implement a provider-specific adapter with its official signature and server-side
payment verification before enabling real checkout. Never trust a browser return.
"""

import hashlib
import hmac
import json
import time
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from operations.calls import create_paid_calls, notify, notify_admins

from .commerce import check_policy
from .models import CommercePolicy, Order, Payment, PaymentEvent
from .views import audit


def sandbox_enabled():
    return (
        settings.DEBUG and settings.PAYMENT_MODE == "sandbox" and len(settings.SANDBOX_PAYMENT_SECRET) >= 32
    )


@transaction.atomic
def start_checkout(user, project_id):
    if not sandbox_enabled():
        raise ValidationError(
            "Checkout is not open yet. The team is configuring payment and commercial terms."
        )
    order = Order.objects.select_for_update().get(project_id=project_id, project__client__user=user)
    check_policy(CommercePolicy.objects.filter(pk=1).first())
    if not order.terms_snapshot.get("quote_id") or not order.total_minor:
        raise ValidationError("Review and accept a quote before starting checkout.")
    if order.payment_status == "confirmed" or order.project.status != "payment_pending":
        raise ValidationError("This order is not awaiting payment.")
    existing = order.payments.first()
    if existing:
        return existing
    payment = Payment.objects.create(
        order=order,
        provider="sandbox",
        provider_reference=f"sandbox_{uuid.uuid4().hex}",
        amount_minor=order.total_minor,
        currency=order.currency,
    )
    audit(user, "payment.started", payment.id, {"provider": "sandbox"})
    return payment


def verify_sandbox_event(body, signature):
    if not sandbox_enabled():
        raise ValidationError("Payment gateway is disabled.")
    if len(body) > 16384:
        raise ValidationError("Invalid payment event.")
    try:
        stamp, supplied = signature.split(".", 1)
        if abs(time.time() - int(stamp)) > 300:
            raise ValueError
        expected = hmac.new(
            settings.SANDBOX_PAYMENT_SECRET.encode(), stamp.encode() + b"." + body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, supplied):
            raise ValueError
        event = json.loads(body)
        if not isinstance(event, dict) or set(event) != {
            "event_id",
            "reference",
            "order_id",
            "amount_minor",
            "currency",
            "status",
        }:
            raise ValueError
        for key in ["event_id", "reference", "order_id", "currency"]:
            if not isinstance(event[key], str) or not 1 <= len(event[key]) <= 200:
                raise ValueError
        uuid.UUID(event["order_id"])
        if (
            type(event["amount_minor"]) is not int
            or event["amount_minor"] <= 0
            or event["status"] not in ["confirmed", "failed"]
        ):
            raise ValueError
    except (ValueError, TypeError, KeyError, AttributeError):
        raise ValidationError("Invalid payment event or signature.") from None
    return event


@transaction.atomic
def apply_sandbox_event(body, signature):
    # Verification stays inside this boundary: callers cannot supply an unverified event dictionary.
    event = verify_sandbox_event(body, signature)
    order = Order.objects.select_for_update().filter(pk=event["order_id"]).first()
    if not order:
        raise ValidationError("Unknown payment order.")
    payment = Payment.objects.filter(
        order=order, provider="sandbox", provider_reference=event["reference"]
    ).first()
    if (
        not payment
        or payment.amount_minor != event["amount_minor"]
        or payment.currency != event["currency"]
        or order.total_minor != payment.amount_minor
        or order.currency != payment.currency
    ):
        raise ValidationError("Payment does not match its order, amount and currency.")
    digest = hashlib.sha256(body).hexdigest()
    previous = PaymentEvent.objects.filter(provider="sandbox", event_id=event["event_id"]).first()
    if previous:
        if previous.payload_digest != digest or previous.payment_id != payment.id:
            raise ValidationError("Conflicting duplicate payment event.")
        return previous
    project = order.project
    if event["status"] == "confirmed" and payment.status != "confirmed":
        if project.status != "payment_pending" or order.payment_status == "confirmed":
            raise ValidationError("Payment needs reconciliation; project cannot be activated.")
        now = timezone.now()
        payment.status, payment.confirmed_at = "confirmed", now
        order.payment_status = "confirmed"
        project.status, project.payment_completed_at = "payment_completed", now
        # Do not manufacture a deadline until D06 has an approved executable rule.
        project.save(update_fields=["status", "payment_completed_at", "updated_at"])
        create_paid_calls(project)
        notify(
            project.client.user,
            project,
            f"payment:{payment.pk}:client",
            "Payment confirmed. Your project is ready for assignment.",
        )
        notify_admins(
            project, f"payment:{payment.pk}", "A project payment was confirmed and is ready for assignment."
        )
        audit(None, "payment.confirmed", payment.id, {"provider": "sandbox", "project": str(project.id)})
    elif event["status"] == "failed" and payment.status != "confirmed":
        payment.status, order.payment_status = "failed", "failed"
        audit(None, "payment.failed", payment.id, {"provider": "sandbox"})
    payment.save(update_fields=["status", "confirmed_at", "updated_at"])
    order.save(update_fields=["payment_status", "updated_at"])
    return PaymentEvent.objects.create(
        provider="sandbox",
        event_id=event["event_id"],
        payment=payment,
        payload_digest=digest,
        outcome=event["status"],
    )
