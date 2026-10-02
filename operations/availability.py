"""Derived editor availability from current, non-terminal assignments."""

from core.models import Project

from .models import EditorAssignment

TERMINAL_PROJECT_STATUSES = [Project.Status.COMPLETED, Project.Status.CANCELLED]


def active_project_count(editor):
    """Count the editor's current assignments whose projects are still active."""

    if hasattr(editor, "active_count"):
        return editor.active_count
    return (
        EditorAssignment.objects.filter(editor=editor, ended_at__isnull=True)
        .exclude(project__status__in=TERMINAL_PROJECT_STATUSES)
        .count()
    )


def availability_state(editor):
    """Return the single read-only availability representation used by every surface."""

    count = active_project_count(editor)
    unavailable = count > 0
    return {
        "status": "unavailable" if unavailable else "available",
        "label": "Unavailable" if unavailable else "Available",
        "icon": "🔴" if unavailable else "✅",
        "active_count": count,
        "summary": (
            f"Unavailable — {count} active project{'s' if count != 1 else ''}"
            if unavailable
            else "Available — no active projects"
        ),
    }
