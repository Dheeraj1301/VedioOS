"""Protected order-reconciliation queries for the admin workspace."""

import uuid
from datetime import datetime

from django.db.models import Count, Q
from django.http import Http404
from django.utils import timezone

from core.models import Order, Project

ORDER_PAYMENT_STATES = tuple(value for value, _label in Order._meta.get_field("payment_status").choices)
PROJECT_WORKFLOW_STATES = tuple(Project.Status.choices)


def order_page(before=None, payment="all", workflow="all", search="", size=50):
    """Return a stable, annotated page using server-owned order fields."""
    search = search.strip() if isinstance(search, str) else ""
    if len(search) > 120:
        raise Http404("Invalid order search.")

    rows = (
        Order.objects.select_related("project__client__user", "plan")
        .annotate(payment_attempt_count=Count("payments", distinct=True))
        .order_by("-created_at", "-id")
    )
    if search:
        rows = rows.filter(
            Q(project__title__icontains=search)
            | Q(project__client__user__name__icontains=search)
            | Q(project__client__user__email__icontains=search)
        )

    if payment == "paid":
        payment = "confirmed"
    if payment == "unpaid":
        rows = rows.exclude(payment_status="confirmed")
    elif payment in ORDER_PAYMENT_STATES:
        rows = rows.filter(payment_status=payment)
    else:
        payment = "all"

    workflow_values = {value for value, _label in PROJECT_WORKFLOW_STATES}
    if workflow in workflow_values:
        rows = rows.filter(project__status=workflow)
    else:
        workflow = "all"

    if before:
        if not isinstance(before, str) or len(before) > 100:
            raise Http404("Invalid order page.")
        try:
            stamp, key = before.split("|", 1)
            created_at, order_id = datetime.fromisoformat(stamp), uuid.UUID(key)
        except (ValueError, TypeError):
            raise Http404("Invalid order page.") from None
        if timezone.is_naive(created_at):
            raise Http404("Invalid order page.")
        rows = rows.filter(Q(created_at__lt=created_at) | Q(created_at=created_at, id__lt=order_id))

    batch = list(rows[: size + 1])
    current = batch[:size]
    older = None
    if len(batch) > size:
        last = current[-1]
        older = f"{last.created_at.isoformat()}|{last.id}"
    return current, older, payment, workflow, search
