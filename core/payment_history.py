"""Protected, stable payment-ledger queries for clients and administrators."""

import uuid
from datetime import datetime, timedelta

from django.db.models import Q
from django.http import Http404
from django.utils import timezone

from .models import Payment

PAYMENT_STATUSES = ("pending", "confirmed", "failed", "refunded")
PAYMENT_DATE_RANGES = {
    "all": ("All dates", None),
    "5": ("Last 5 days", 5),
    "10": ("Last 10 days", 10),
    "30": ("Last 30 days", 30),
    "90": ("Last 90 days", 90),
    "365": ("Last year", 365),
}


def payment_page(user, before=None, status="all", size=50, query="", date_range="all"):
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
    query = query.strip() if isinstance(query, str) else ""
    if len(query) > 120:
        raise Http404("Invalid payment search.")
    if query:
        search = Q(order__project__title__icontains=query) | Q(
            provider_reference__icontains=query
        )
        try:
            identifier = uuid.UUID(query)
        except (ValueError, TypeError, AttributeError):
            pass
        else:
            search |= Q(pk=identifier) | Q(order_id=identifier)
        rows = rows.filter(search)
    if date_range not in PAYMENT_DATE_RANGES:
        date_range = "all"
    days = PAYMENT_DATE_RANGES[date_range][1]
    if days:
        rows = rows.filter(created_at__gte=timezone.now() - timedelta(days=days))
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
