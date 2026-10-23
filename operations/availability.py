"""Workload-derived availability plus an explicit Admin-only override."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from core.models import Project, User
from core.views import audit

from .models import Editor, EditorAssignment, EditorAvailabilityRequest, Notification

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
    """Return the authoritative status and any separately pending editor request."""

    count = active_project_count(editor)
    pending = editor.availability_requests.filter(
        status=EditorAvailabilityRequest.Status.PENDING
    ).first()
    if editor.availability_override == Editor.AvailabilityOverride.NOT_AVAILABLE:
        status, label, icon = "not_available", "Not Available", "🔴"
        summary = "Not Available — set by Admin"
    elif count:
        status, label, icon = "busy", "Unavailable (Busy)", "🟠"
        summary = f"Unavailable (Busy) — {count} active project{'s' if count != 1 else ''}"
    else:
        status, label, icon = "available", "Available", "✅"
        summary = "Available — no active projects"
    return {
        "status": status,
        "label": label,
        "icon": icon,
        "active_count": count,
        "summary": summary,
        "pending_request": bool(pending),
        "pending_reason": pending.reason if pending else "",
    }


def _admin_only(user):
    if not user or not user.is_active or user.role != "admin":
        raise PermissionDenied


@transaction.atomic
def request_not_available(user, reason):
    if not user or not user.is_active or user.role != "editor":
        raise PermissionDenied
    reason = reason.strip()
    if not reason:
        raise ValidationError("Provide a reason for your Not Available request.")
    if len(reason) > 300:
        raise ValidationError("Keep the availability reason to 300 characters or fewer.")
    editor = Editor.objects.select_for_update().get(user=user)
    if editor.availability_override == Editor.AvailabilityOverride.NOT_AVAILABLE:
        raise ValidationError("Admin has already set your status to Not Available.")
    request_record, created = EditorAvailabilityRequest.objects.update_or_create(
        editor=editor,
        status=EditorAvailabilityRequest.Status.PENDING,
        defaults={"requested_status": "not_available", "reason": reason},
    )
    message = (
        f"{editor.user.name} ({editor.login_id}) requested Not Available. Reason: {reason}"
    )
    for admin in User.objects.filter(
        role="admin", is_active=True, auth_deleted_at__isnull=True
    ):
        Notification.objects.update_or_create(
            event_key=f"editor-availability-request:{request_record.pk}:admin:{admin.pk}",
            defaults={
                "recipient": admin,
                "reference_type": Notification.ReferenceType.EDITOR,
                "reference_id": editor.pk,
                "message": message,
            },
        )
    audit(
        user,
        "editor.availability_requested" if created else "editor.availability_request_updated",
        editor.pk,
        {"request": str(request_record.pk), "requested_status": "not_available"},
    )
    return request_record


@transaction.atomic
def set_availability_override(user, editor_id, status, reason):
    _admin_only(user)
    reason = reason.strip()
    if not reason:
        raise ValidationError("Provide a reason for this availability decision.")
    if len(reason) > 300:
        raise ValidationError("Keep the availability reason to 300 characters or fewer.")
    if status not in {
        Editor.AvailabilityOverride.AUTOMATIC,
        Editor.AvailabilityOverride.NOT_AVAILABLE,
    }:
        raise ValidationError("Choose a valid availability status.")
    editor = Editor.objects.select_for_update().select_related("user").get(pk=editor_id)
    editor.availability_override = status
    editor.availability_override_reason = reason if status else ""
    editor.availability_override_by = user if status else None
    editor.availability_override_at = timezone.now() if status else None
    editor.save(
        update_fields=[
            "availability_override",
            "availability_override_reason",
            "availability_override_by",
            "availability_override_at",
            "updated_at",
        ]
    )
    pending = editor.availability_requests.select_for_update().filter(
        status=EditorAvailabilityRequest.Status.PENDING
    )
    pending.update(
        status=(
            EditorAvailabilityRequest.Status.APPLIED
            if status == Editor.AvailabilityOverride.NOT_AVAILABLE
            else EditorAvailabilityRequest.Status.DECLINED
        ),
        decided_by=user,
        decided_at=timezone.now(),
        updated_at=timezone.now(),
    )
    label = "Not Available" if status else "Automatic availability"
    Notification.objects.create(
        recipient=editor.user,
        event_key=f"editor-availability-decision:{editor.pk}:{timezone.now().timestamp()}",
        message=f"Admin set your status to {label}. Reason: {reason}",
    )
    audit(
        user,
        "editor.availability_override_changed",
        editor.pk,
        {"status": status or "automatic", "reason": reason},
    )
    return editor
