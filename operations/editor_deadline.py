"""24-hour editor deadline: assignment email, 12h and 6h reminders, and dashboard countdown data."""

from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMessage
from django.urls import reverse
from django.utils import timezone

from core.models import Project

from .models import AuditLog, EditorAssignment

DEADLINE = timedelta(hours=24)
# (hours remaining at or below which the stage is due, stage name)
STAGES = ((24, "assigned"), (12, "12h"), (6, "6h"))
EMAIL_ACTION = "assignment.deadline_email"


def schedule_deadline_alarms(assignment):
    """Wake the site when 12 and 6 hours remain (one minute late, so the stage is surely due)."""
    from core.qstash import schedule_sweep

    for hours_left in (12, 6):
        run_at = deadline_for(assignment) - timedelta(hours=hours_left) + timedelta(minutes=1)
        schedule_sweep(run_at, f"assignment-{assignment.pk}-{hours_left}h")


def deadline_for(assignment):
    return assignment.created_at + DEADLINE


def time_left_label(due_at, now=None):
    seconds = int((due_at - (now or timezone.now())).total_seconds())
    if seconds <= 0:
        return "Time is up"
    hours, minutes = divmod(seconds // 60, 60)
    return f"{hours}h {minutes:02d}m left"


def attach_deadlines(projects):
    """Set editor_deadline_at and editor_time_left on projects that have a current assignment and no V1 yet."""
    rows = list(projects)
    current = {
        a.project_id: deadline_for(a)
        for a in EditorAssignment.objects.filter(project_id__in=[p.pk for p in rows], ended_at__isnull=True)
    }
    submitted = set(Project.objects.filter(pk__in=list(current), versions__number=1).values_list("pk", flat=True))
    for project in rows:
        due_at = current.get(project.pk) if project.pk not in submitted else None
        project.editor_deadline_at = due_at
        project.editor_time_left = time_left_label(due_at) if due_at else ""
    return rows


def _message(assignment, stage, due_at):
    project = assignment.project
    link = settings.PUBLIC_SITE_URL + reverse("editor_project", args=[project.pk])
    when = f"{timezone.localtime(due_at):%d %b %Y, %H:%M} ({timezone.get_current_timezone_name()})"
    if stage == "assigned":
        subject = f"New BRIO project assigned: {project.title}"
        opening = "You have been assigned a new project. You have 24 hours to complete the first draft."
    else:
        hours = stage.rstrip("h")
        subject = f"{hours} hours left on {project.title}"
        opening = f"Reminder: about {hours} hours remain to complete the first draft of this project."
    body = (
        f"Hello {assignment.editor.user.name or 'there'},\n\n{opening}\n\n"
        f"Project: {project.title}\nDue: {when}\n\nOpen the project: {link}\n\nTeam BRIO"
    )
    return subject, body


def send_deadline_emails(now=None, assignment_id=None):
    """Send each due stage once per assignment; return how many emails were delivered."""
    from core.views import audit

    now = now or timezone.now()
    assignments = EditorAssignment.objects.filter(ended_at__isnull=True, created_at__gt=now - DEADLINE).select_related(
        "project", "editor__user"
    )
    if assignment_id:
        assignments = assignments.filter(pk=assignment_id)
    sent_stages = set(
        AuditLog.objects.filter(action=EMAIL_ACTION, target_id__in=[str(a.pk) for a in assignments]).values_list(
            "target_id", "detail__stage"
        )
    )
    delivered = 0
    for assignment in assignments:
        if assignment.project.versions.filter(number=1).exists():
            continue
        due_at = deadline_for(assignment)
        left = due_at - now
        due_stages = [name for hours, name in STAGES if left <= timedelta(hours=hours)]
        # Only the most recent due stage is sent, so a late sweep never sends a burst of reminders.
        stage = due_stages[-1] if due_stages else None
        if not stage or (str(assignment.pk), stage) in sent_stages:
            continue
        ok = False
        if settings.NOTIFICATION_EMAIL_ENABLED and assignment.editor.user.email:
            subject, body = _message(assignment, stage, due_at)
            try:
                ok = EmailMessage(subject, body, settings.DEFAULT_FROM_EMAIL, [assignment.editor.user.email]).send() == 1
            except Exception:
                ok = False
        audit(None, EMAIL_ACTION, assignment.pk, {"stage": stage, "delivered": ok, "project": str(assignment.project_id)})
        delivered += ok
    return delivered
