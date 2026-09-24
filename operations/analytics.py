"""Read-only operational analytics with explicit, reconciliation-friendly formulas."""

from django.db.models import Count, Q
from django.utils import timezone

from core.models import Client, Order, Project

from .models import (
    CallRequest,
    Editor,
    EditorAssignment,
    NotificationDelivery,
    RedemptionRequest,
    SupportRequest,
)


def _rows(choices, counts):
    return [
        {"key": key, "label": label, "count": counts.get(key, 0)}
        for key, label in choices
    ]


def operational_analytics():
    """Return counts only; financial and rate metrics await approved D15 formulas."""

    order_counts = {
        row["payment_status"]: row["count"]
        for row in Order.objects.values("payment_status").annotate(count=Count("id"))
    }
    project_counts = {
        row["status"]: row["count"]
        for row in Project.objects.values("status").annotate(count=Count("id"))
    }
    call_counts = {
        row["status"]: row["count"]
        for row in CallRequest.objects.values("status").annotate(count=Count("id"))
    }
    payout_counts = {
        row["status"]: row["count"]
        for row in RedemptionRequest.objects.values("status").annotate(count=Count("id"))
    }
    delivery_counts = {
        row["state"]: row["count"]
        for row in NotificationDelivery.objects.values("state").annotate(count=Count("id"))
    }
    open_assignments = EditorAssignment.objects.filter(ended_at__isnull=True).exclude(
        project__status__in=[Project.Status.COMPLETED, Project.Status.CANCELLED]
    )
    editor_counts = Editor.objects.aggregate(
        total=Count("id"),
        approved_active=Count("id", filter=Q(approved=True, user__is_active=True)),
        awaiting_approval=Count("id", filter=Q(approved=False)),
        available=Count(
            "id",
            filter=Q(approved=True, user__is_active=True, availability__status="available"),
        ),
    )
    return {
        "generated_at": timezone.now(),
        "headline": {
            "clients": Client.objects.filter(user__is_active=True).count(),
            "orders": sum(order_counts.values()),
            "paid_orders": order_counts.get("confirmed", 0),
            "open_projects": Project.objects.exclude(
                status__in=[Project.Status.COMPLETED, Project.Status.CANCELLED]
            ).count(),
            "completed_projects": project_counts.get(Project.Status.COMPLETED, 0),
            "open_assignments": open_assignments.count(),
            "pending_payouts": payout_counts.get("requested", 0),
            "open_support": SupportRequest.objects.filter(
                status__in=[SupportRequest.Status.OPEN, SupportRequest.Status.IN_PROGRESS]
            ).count(),
        },
        "orders": _rows(Order._meta.get_field("payment_status").choices, order_counts),
        "projects": _rows(Project.Status.choices, project_counts),
        "editors": editor_counts,
        "calls": [
            {"key": key, "label": key.replace("_", " ").title(), "count": count}
            for key, count in sorted(call_counts.items())
        ],
        "payouts": [
            {"key": key, "label": key.replace("_", " ").title(), "count": count}
            for key, count in sorted(payout_counts.items())
        ],
        "deliveries": _rows(NotificationDelivery.State.choices, delivery_counts),
    }
