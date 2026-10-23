"""Archive application access after a linked Supabase Auth identity is deleted."""

import uuid
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Project, ProjectStorageCleanup, User


class SupabaseDeletionSyncUnavailable(Exception):
    pass


def active_supabase_auth_ids():
    """Fetch a complete Auth inventory through the server-only Admin API."""
    if not settings.SUPABASE_AUTH_URL or not settings.SUPABASE_SECRET_KEY:
        raise SupabaseDeletionSyncUnavailable("Supabase deletion sync is not configured.")
    active_ids = set()
    page = 1
    while True:
        try:
            response = requests.get(
                urljoin(settings.SUPABASE_AUTH_URL.rstrip("/") + "/", "auth/v1/admin/users"),
                params={"page": page, "per_page": 1000},
                headers={
                    "apikey": settings.SUPABASE_SECRET_KEY,
                    "Authorization": f"Bearer {settings.SUPABASE_SECRET_KEY}",
                },
                timeout=settings.SUPABASE_AUTH_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            raise SupabaseDeletionSyncUnavailable("Supabase Auth could not be reached.") from exc
        if response.status_code != 200:
            raise SupabaseDeletionSyncUnavailable("Supabase Auth inventory was unavailable.")
        try:
            body = response.json()
        except ValueError as exc:
            raise SupabaseDeletionSyncUnavailable("Supabase Auth returned invalid data.") from exc
        users = body.get("users")
        if not isinstance(users, list):
            raise SupabaseDeletionSyncUnavailable("Supabase Auth returned incomplete data.")
        for identity in users:
            try:
                active_ids.add(uuid.UUID(str(identity.get("id"))))
            except (AttributeError, TypeError, ValueError):
                raise SupabaseDeletionSyncUnavailable(
                    "Supabase Auth returned an invalid identity."
                ) from None
        if len(users) < 1000:
            return active_ids
        page += 1


def synchronize_supabase_deletions():
    active_ids = active_supabase_auth_ids()
    linked = User.objects.filter(
        supabase_auth_user_id__isnull=False,
        auth_deleted_at__isnull=True,
    ).values_list("id", "supabase_auth_user_id")
    archived = 0
    blocked = 0
    for user_id, auth_id in linked:
        if auth_id in active_ids:
            continue
        try:
            archive_deleted_identity(user_id)
        except ValidationError:
            blocked += 1
        else:
            archived += 1
    if blocked:
        raise SupabaseDeletionSyncUnavailable(
            "Supabase removed the last active administrator; manual recovery is required."
        )
    return {"archived": archived, "blocked": blocked}


@transaction.atomic
def archive_deleted_identity(user_id, *, deleted_at=None):
    """Apply the durable, non-destructive deletion policy for one local user."""
    from operations.models import (
        AssignmentQueue,
        AuditLog,
        CallRequest,
        EditorAssignment,
        RoundRobinState,
    )

    user = User.objects.select_for_update().get(pk=user_id)
    deleted_at = deleted_at or timezone.now()
    if user.auth_deleted_at:
        return user

    if user.role == User.Role.ADMIN:
        active_admins = User.objects.filter(
            role=User.Role.ADMIN,
            is_active=True,
            auth_deleted_at__isnull=True,
            admin_profile__isnull=False,
        ).count()
        if active_admins <= 1:
            raise ValidationError("The last active administrator cannot be deleted.")

    if user.role == User.Role.CLIENT and hasattr(user, "client_profile"):
        projects = Project.objects.select_for_update().filter(
            client=user.client_profile,
            archived_at__isnull=True,
        )
        project_ids = list(projects.values_list("pk", flat=True))
        projects.update(archived_at=deleted_at, updated_at=deleted_at)
        ProjectStorageCleanup.objects.bulk_create(
            [ProjectStorageCleanup(project_id=project_id) for project_id in project_ids],
            ignore_conflicts=True,
        )

    if user.role == User.Role.EDITOR and hasattr(user, "editor_profile"):
        editor = user.editor_profile
        assignments = EditorAssignment.objects.select_for_update().filter(
            editor=editor,
            ended_at__isnull=True,
        )
        project_ids = list(assignments.values_list("project_id", flat=True))
        assignments.update(ended_at=deleted_at, updated_at=deleted_at)
        Project.objects.filter(pk__in=project_ids).exclude(
            status__in=[Project.Status.COMPLETED, Project.Status.CANCELLED]
        ).update(status=Project.Status.WAITING, updated_at=deleted_at)
        AssignmentQueue.objects.filter(project_id__in=project_ids).update(
            status="waiting",
            blocked_reason="Editor identity was removed; reassignment is required.",
            updated_at=deleted_at,
        )
        CallRequest.objects.filter(editor=editor).update(editor=None, updated_at=deleted_at)
        RoundRobinState.objects.filter(last_editor=editor).update(last_editor=None)

    user.is_active = False
    user.auth_deleted_at = deleted_at
    user.active_session_key = ""
    user.save(update_fields=["is_active", "auth_deleted_at", "active_session_key"])
    AuditLog.objects.create(
        actor=None,
        action="identity.supabase_deleted",
        target_id=str(user.pk),
        detail={"role": user.role, "provider": "supabase_auth"},
    )
    return user
