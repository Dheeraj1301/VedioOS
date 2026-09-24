"""Protected client-roster queries for the admin workspace."""

import uuid
from datetime import datetime

from django.db.models import Count, Max, Q
from django.http import Http404
from django.utils import timezone

from core.models import Client, Project

from .models import SupportRequest

CLIENT_STATES = (
    ("active", "Active"),
    ("awaiting_verification", "Awaiting email verification"),
    ("inactive", "Inactive"),
)
OPEN_PROJECT_STATES = tuple(
    value
    for value, _label in Project.Status.choices
    if value not in {Project.Status.COMPLETED, Project.Status.CANCELLED}
)
OPEN_SUPPORT_STATES = (SupportRequest.Status.OPEN, SupportRequest.Status.IN_PROGRESS)


def client_page(before=None, state="all", search="", size=50):
    """Return a stable, annotated client page plus normalized filters."""
    search = search.strip() if isinstance(search, str) else ""
    if len(search) > 120:
        raise Http404("Invalid client search.")

    clients = (
        Client.objects.select_related("user")
        .annotate(
            project_count=Count("projects", distinct=True),
            open_project_count=Count(
                "projects", filter=Q(projects__status__in=OPEN_PROJECT_STATES), distinct=True
            ),
            completed_project_count=Count(
                "projects", filter=Q(projects__status=Project.Status.COMPLETED), distinct=True
            ),
            confirmed_order_count=Count(
                "projects__order",
                filter=Q(projects__order__payment_status="confirmed"),
                distinct=True,
            ),
            open_support_count=Count(
                "support_requests",
                filter=Q(support_requests__status__in=OPEN_SUPPORT_STATES),
                distinct=True,
            ),
            last_project_at=Max("projects__created_at"),
        )
        .order_by("-created_at", "-id")
    )
    if search:
        clients = clients.filter(Q(user__name__icontains=search) | Q(user__email__icontains=search))

    if state == "active":
        clients = clients.filter(user__is_active=True)
    elif state == "awaiting_verification":
        clients = clients.filter(user__is_active=False, user__email_verified_at__isnull=True)
    elif state == "inactive":
        clients = clients.filter(user__is_active=False, user__email_verified_at__isnull=False)
    else:
        state = "all"

    if before:
        if not isinstance(before, str) or len(before) > 100:
            raise Http404("Invalid client page.")
        try:
            stamp, key = before.split("|", 1)
            created_at, client_id = datetime.fromisoformat(stamp), uuid.UUID(key)
        except (ValueError, TypeError):
            raise Http404("Invalid client page.") from None
        if timezone.is_naive(created_at):
            raise Http404("Invalid client page.")
        clients = clients.filter(
            Q(created_at__lt=created_at) | Q(created_at=created_at, id__lt=client_id)
        )

    batch = list(clients[: size + 1])
    current = batch[:size]
    older = None
    if len(batch) > size:
        last = current[-1]
        older = f"{last.created_at.isoformat()}|{last.id}"
    return current, older, state, search
