"""Read-only V1 timing and visibility helpers."""

from datetime import timedelta

from django.utils import timezone

from operations.models import AuditLog


def v1_status(project):
    """Return the first submitted version and its saved editing-hours target."""
    version = project.versions.select_related("file").filter(number=1).first()
    terms = getattr(getattr(project, "order", None), "terms_snapshot", {}) or {}
    hours = terms.get("delivery_hours")
    if type(hours) is not int or hours <= 0:
        hours = None
    started_at = (
        AuditLog.objects.filter(
            action="project.editing_started",
            target_id=str(project.pk),
        )
        .order_by("created_at")
        .values_list("created_at", flat=True)
        .first()
    )
    due_at = started_at + timedelta(hours=hours) if started_at and hours else None
    return {
        "v1_version": version,
        "v1_editing_hours": hours,
        "v1_started_at": started_at,
        "v1_due_at": due_at,
        "v1_overdue": bool(due_at and not version and due_at < timezone.now()),
    }


def attach_v1_status(projects):
    """Attach display-only V1 fields to a small dashboard project collection."""
    rows = list(projects)
    for project in rows:
        for key, value in v1_status(project).items():
            setattr(project, key, value)
    return rows
