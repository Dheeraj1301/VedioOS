"""Payment boundary. Only a signed development gateway is implemented so far.

Implement a provider-specific adapter with its official signature and server-side
payment verification before enabling real checkout. Never trust a browser return.
"""

import hashlib
import hmac
import json
import time
import uuid

import requests
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from requests import RequestException

from operations.calls import create_paid_calls, notify, notify_admins

from .commerce import check_policy
from .models import CommercePolicy, Order, Payment, PaymentEvent
from .views import audit


def sandbox_enabled():
    return (
        settings.DEBUG and settings.PAYMENT_MODE == "sandbox" and len(settings.SANDBOX_PAYMENT_SECRET) >= 32
    )


def razorpay_test_enabled():
    return (
        settings.DEBUG
        and settings.PAYMENT_MODE == "razorpay_test"
        and settings.RAZORPAY_KEY_ID.startswith("rzp_test_")
        and len(settings.RAZORPAY_KEY_SECRET) >= 16
        and settings.RAZORPAY_API_BASE == "https://api.razorpay.com/v1"
    )


def _razorpay_request(method, path, **kwargs):
    if not razorpay_test_enabled():
        raise ValidationError("Payment checkout is not configured.")
    try:
        response = requests.request(
            method,
            f"{settings.RAZORPAY_API_BASE}/{path.lstrip('/')}",
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
            timeout=15,
            **kwargs,
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError
        return data
    except (RequestException, ValueError):
        raise ValidationError("Payment checkout is unavailable. Please try again.") from None


@transaction.atomic
def start_checkout(user, project_id):
    if not sandbox_enabled() and not razorpay_test_enabled():
        raise ValidationError(
            "Checkout is not open yet. The team is configuring payment and commercial terms."
        )
    order = Order.objects.select_for_update().get(project_id=project_id, project__client__user=user)
    check_policy(CommercePolicy.objects.filter(pk=1).first())
    if not order.terms_snapshot.get("quote_id") or not order.total_minor:
        raise ValidationError("Review and accept a quote before starting checkout.")
    if order.payment_status == "confirmed" or order.project.status != "payment_pending":
        raise ValidationError("This order is not awaiting payment.")
    existing = order.payments.filter(status="pending").first()
    if existing:
        return existing
    if razorpay_test_enabled():
        gateway_order = _razorpay_request(
            "POST",
            "orders",
            json={
                "amount": order.total_minor,
                "currency": order.currency,
                "receipt": f"vedioos_{order.pk.hex[:24]}",
                "notes": {"vedioos_order_id": str(order.pk)},
            },
        )
        reference = gateway_order.get("id")
        if (
            not isinstance(reference, str)
            or not reference.startswith("order_")
            or gateway_order.get("amount") != order.total_minor
            or gateway_order.get("currency") != order.currency
            or gateway_order.get("status") != "created"
        ):
            raise ValidationError("The payment provider returned an invalid order.")
        provider = "razorpay_test"
    else:
        provider = "sandbox"
        reference = f"sandbox_{uuid.uuid4().hex}"
    payment = Payment.objects.create(
        order=order,
        provider=provider,
        provider_reference=reference,
        amount_minor=order.total_minor,
        currency=order.currency,
    )
    audit(user, "payment.started", payment.id, {"provider": provider})
    return payment


def razorpay_checkout_data(payment):
    if not razorpay_test_enabled() or payment.provider != "razorpay_test":
        raise ValidationError("Payment checkout is unavailable.")
    if payment.status != "pending" or payment.order.payment_status == "confirmed":
        raise ValidationError("This payment is not awaiting checkout.")
    return {
        "key": settings.RAZORPAY_KEY_ID,
        "amount": payment.amount_minor,
        "currency": payment.currency,
        "order_id": payment.provider_reference,
        "payment_id": str(payment.pk),
    }


@transaction.atomic
def confirm_razorpay_test_payment(user, payment_id, payload):
    if not razorpay_test_enabled() or not isinstance(payload, dict) or set(payload) != {
        "razorpay_payment_id",
        "razorpay_order_id",
        "razorpay_signature",
    }:
        raise ValidationError("Invalid Razorpay payment response.")
    payment = (
        Payment.objects.select_for_update()
        .select_related("order__project__client__user")
        .filter(pk=payment_id, order__project__client__user=user, provider="razorpay_test")
        .first()
    )
    if not payment:
        raise ValidationError("Unknown Razorpay payment.")
    gateway_payment_id = payload.get("razorpay_payment_id")
    supplied_order_id = payload.get("razorpay_order_id")
    signature = payload.get("razorpay_signature")
    if any(
        not isinstance(value, str) or not 1 <= len(value) <= 200
        for value in [gateway_payment_id, supplied_order_id, signature]
    ):
        raise ValidationError("Invalid Razorpay payment response.")
    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        f"{payment.provider_reference}|{gateway_payment_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    if supplied_order_id != payment.provider_reference or not hmac.compare_digest(expected, signature):
        raise ValidationError("Razorpay payment signature was rejected.")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(canonical).hexdigest()
    previous = PaymentEvent.objects.filter(
        provider="razorpay_test", event_id=gateway_payment_id
    ).first()
    if previous:
        if previous.payload_digest != digest or previous.payment_id != payment.id:
            raise ValidationError("Conflicting Razorpay payment response.")
        return previous
    if payment.status != "pending":
        raise ValidationError("This payment session is no longer active.")
    gateway_payment = _razorpay_request("GET", f"payments/{gateway_payment_id}")
    if (
        gateway_payment.get("id") != gateway_payment_id
        or gateway_payment.get("order_id") != payment.provider_reference
        or gateway_payment.get("amount") != payment.amount_minor
        or gateway_payment.get("currency") != payment.currency
        or gateway_payment.get("status") != "captured"
        or gateway_payment.get("captured") is not True
    ):
        raise ValidationError("Razorpay payment is not captured or does not match this order.")
    order = payment.order
    project = order.project
    if payment.status != "confirmed":
        if project.status != "payment_pending" or order.payment_status == "confirmed":
            raise ValidationError("Payment needs reconciliation; project cannot be activated.")
        now = timezone.now()
        payment.status, payment.confirmed_at = "confirmed", now
        order.payment_status = "confirmed"
        project.status, project.payment_completed_at = "payment_completed", now
        project.save(update_fields=["status", "payment_completed_at", "updated_at"])
        create_paid_calls(project)
        notify(
            project.client.user,
            project,
            f"payment:{payment.pk}:client",
            "Razorpay test payment confirmed. Your project remains in test-payment mode.",
        )
        notify_admins(
            project,
            f"payment:{payment.pk}",
            "A Razorpay test payment was confirmed. It is not production revenue.",
        )
        audit(
            None,
            "payment.confirmed",
            payment.id,
            {"provider": "razorpay_test", "project": str(project.id)},
        )
    payment.save(update_fields=["status", "confirmed_at", "updated_at"])
    order.save(update_fields=["payment_status", "updated_at"])
    return PaymentEvent.objects.create(
        provider="razorpay_test",
        event_id=gateway_payment_id,
        payment=payment,
        payload_digest=digest,
        outcome="confirmed",
    )


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
