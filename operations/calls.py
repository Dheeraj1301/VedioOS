"""Paid consultation requests and admin scheduling; no meeting provider is implied."""

from datetime import timezone as datetime_timezone

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from core.models import User
from core.views import audit

from .models import CallRequest, Editor, Notification


def notify(recipient, project, key, message):
    Notification.objects.get_or_create(
        event_key=key,
        defaults={"recipient": recipient, "project": project, "message": message},
    )


def notify_admins(project, key, message):
    for admin in User.objects.filter(role="admin", is_active=True):
        notify(admin, project, f"{key}:admin:{admin.pk}", message)


def create_paid_calls(project):
    """Called in the same transaction as the first verified payment confirmation."""
    for stage, selected in (("before", project.call_before), ("after", project.call_after)):
        if not selected:
            continue
        call, created = CallRequest.objects.get_or_create(
            project=project,
            stage=stage,
            defaults={"requested_by": project.client.user},
        )
        if created:
            label = call.get_stage_display()
            notify_admins(project, f"call:{call.pk}:requested", f"Consultation requested: {label}.")
            notify(
                project.client.user,
                project,
                f"call:{call.pk}:client-requested",
                f"Your {label.lower()} consultation request is awaiting scheduling.",
            )
            audit(
                project.client.user, "call.requested", call.pk, {"project": str(project.pk), "stage": stage}
            )


@transaction.atomic
def schedule_call(admin, call_id, editor_id, scheduled_at):
    if not admin.is_active or admin.role != "admin":
        raise PermissionDenied
    call = CallRequest.objects.select_for_update().select_related("project__client__user").get(pk=call_id)
    if call.status == "completed":
        raise ValidationError("A completed consultation cannot be rescheduled.")
    if call.project.order.payment_status != "confirmed":
        raise ValidationError("Consultations require confirmed payment.")
    if call.stage == "after" and not call.project.versions.exists():
        raise ValidationError("Submit a draft before scheduling the after-draft consultation.")
    editor = (
        Editor.objects.filter(pk=editor_id, approved=True, user__is_active=True)
        .select_related("user")
        .first()
    )
    if not editor:
        raise ValidationError("Choose an approved, active editor.")
    if not scheduled_at or timezone.is_naive(scheduled_at) or scheduled_at <= timezone.now():
        raise ValidationError("Choose a future date and time in UTC.")
    if call.status == "scheduled" and call.editor_id == editor.id and call.scheduled_at == scheduled_at:
        return call
    previous_editor_id = call.editor_id
    call.editor, call.scheduled_at, call.status = editor, scheduled_at, "scheduled"
    call.save(update_fields=["editor", "scheduled_at", "status", "updated_at"])
    key = f"call:{call.pk}:schedule:{call.updated_at.isoformat()}"
    when = timezone.localtime(scheduled_at, datetime_timezone.utc).strftime("%d %b %Y %H:%M UTC")
    notify(
        call.project.client.user,
        call.project,
        f"{key}:client",
        f"Your {call.get_stage_display().lower()} consultation is scheduled for {when}.",
    )
    # The consultant may not be assigned to this project's files.
    notify(
        editor.user,
        None,
        f"{key}:editor",
        f"You have a consultation scheduled for {when}. See Calls in your workspace.",
    )
    if previous_editor_id and previous_editor_id != editor.id:
        previous = Editor.objects.select_related("user").get(pk=previous_editor_id)
        notify(
            previous.user,
            None,
            f"{key}:previous",
            "A consultation assigned to you was rescheduled with another editor.",
        )
    audit(
        admin,
        "call.scheduled",
        call.pk,
        {"project": str(call.project_id), "editor": str(editor.id), "scheduled_at": scheduled_at.isoformat()},
    )
    return call


@transaction.atomic
def complete_call(admin, call_id):
    if not admin.is_active or admin.role != "admin":
        raise PermissionDenied
    call = (
        CallRequest.objects.select_for_update()
        .select_related("project__client__user", "editor__user")
        .get(pk=call_id)
    )
    if call.status == "completed":
        return call
    if call.status != "scheduled" or not call.editor_id:
        raise ValidationError("Schedule this consultation before marking it complete.")
    call.status = "completed"
    call.save(update_fields=["status", "updated_at"])
    notify(
        call.project.client.user,
        call.project,
        f"call:{call.pk}:completed:client",
        "Your consultation has been marked complete.",
    )
    notify(
        call.editor.user,
        None,
        f"call:{call.pk}:completed:editor",
        "Your consultation has been marked complete.",
    )
    audit(admin, "call.completed", call.pk, {"project": str(call.project_id)})
    return call
