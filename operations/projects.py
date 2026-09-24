"""Protected project-operations queries for administrators."""

import uuid
from datetime import datetime

from django.db.models import Count, Exists, OuterRef, Q, Subquery
from django.http import Http404
from django.utils import timezone

from core.models import Project
from core.permissions import visible_projects

from .models import EditorAssignment

PROJECT_QUEUES = (
    ("all", "All"),
    ("unassigned", "Unassigned"),
    ("active", "Active"),
    ("review", "Review"),
    ("revision", "Revision"),
    ("overdue", "Overdue"),
    ("completed", "Completed"),
)
TERMINAL_STATES = (Project.Status.COMPLETED, Project.Status.CANCELLED)


def project_page(user, before=None, queue="all", search="", size=50):
    """Return a stable operational project page for an administrator."""
    if user.role != "admin":
        raise Http404("Project queue not found.")
    search = search.strip() if isinstance(search, str) else ""
    if len(search) > 120:
        raise Http404("Invalid project search.")

    current_assignment = EditorAssignment.objects.filter(
        project=OuterRef("pk"), ended_at__isnull=True
    )
    rows = (
        visible_projects(user)
        .select_related("client__user", "order")
        .annotate(
            has_editor=Exists(current_assignment),
            current_editor_name=Subquery(current_assignment.values("editor__user__name")[:1]),
            ready_file_count=Count("files", filter=Q(files__state="ready"), distinct=True),
            open_revision_count=Count(
                "revisions",
                filter=Q(revisions__status__in=["requested", "in_progress"]),
                distinct=True,
            ),
        )
        .order_by("-created_at", "-id")
    )
    if search:
        rows = rows.filter(
            Q(title__icontains=search)
            | Q(client__user__name__icontains=search)
            | Q(client__user__email__icontains=search)
        )

    if queue == "unassigned":
        rows = rows.filter(order__payment_status="confirmed", has_editor=False).exclude(
            status__in=TERMINAL_STATES
        )
    elif queue == "active":
        rows = rows.filter(status__in=[Project.Status.ASSIGNED, Project.Status.EDITING])
    elif queue == "review":
        rows = rows.filter(status=Project.Status.REVIEW)
    elif queue == "revision":
        rows = rows.filter(status__in=[Project.Status.REVISION_REQUESTED, Project.Status.REVISING])
    elif queue == "overdue":
        rows = rows.filter(
            order__payment_status="confirmed", expected_delivery_at__lt=timezone.now()
        ).exclude(status__in=TERMINAL_STATES)
    elif queue == "completed":
        rows = rows.filter(status=Project.Status.COMPLETED)
    else:
        queue = "all"

    if before:
        if not isinstance(before, str) or len(before) > 100:
            raise Http404("Invalid project page.")
        try:
            stamp, key = before.split("|", 1)
            created_at, project_id = datetime.fromisoformat(stamp), uuid.UUID(key)
        except (ValueError, TypeError):
            raise Http404("Invalid project page.") from None
        if timezone.is_naive(created_at):
            raise Http404("Invalid project page.")
        rows = rows.filter(
            Q(created_at__lt=created_at) | Q(created_at=created_at, id__lt=project_id)
        )

    batch = list(rows[: size + 1])
    current = batch[:size]
    older = None
    if len(batch) > size:
        last = current[-1]
        older = f"{last.created_at.isoformat()}|{last.id}"
    return current, older, queue, search
