"""Protected, stable payment-ledger queries for clients and administrators."""

import uuid
from datetime import datetime

from django.db.models import Q
from django.http import Http404
from django.utils import timezone

from .models import Payment

PAYMENT_STATUSES = ("pending", "confirmed", "failed", "refunded")


def payment_page(user, before=None, status="all", size=50):
    if user.role not in {"client", "admin"}:
        raise Http404("Payment history not found.")
    rows = Payment.objects.select_related("order__project__client__user").order_by(
        "-created_at", "-id"
    )
    if user.role == "client":
        rows = rows.filter(order__project__client__user=user)
    if status in PAYMENT_STATUSES:
        rows = rows.filter(status=status)
    else:
        status = "all"
    if before:
        if not isinstance(before, str) or len(before) > 100:
            raise Http404("Invalid payment page.")
        try:
            stamp, key = before.split("|", 1)
            created_at, payment_id = datetime.fromisoformat(stamp), uuid.UUID(key)
        except (ValueError, TypeError):
            raise Http404("Invalid payment page.") from None
        if timezone.is_naive(created_at):
            raise Http404("Invalid payment page.")
        rows = rows.filter(
            Q(created_at__lt=created_at) | Q(created_at=created_at, id__lt=payment_id)
        )
    batch = list(rows[: size + 1])
    current = batch[:size]
    older = None
    if len(batch) > size:
        last = current[-1]
        older = f"{last.created_at.isoformat()}|{last.id}"
    return current, older, status
