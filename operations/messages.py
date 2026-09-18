"""Project conversation boundary; internal notes never enter client views or notices."""

import uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction

from core.models import Project, User
from core.permissions import project_for, visible_projects
from core.views import audit

from .calls import notify
from .models import EditorAssignment, ProjectMessage


def visible_messages(user, project):
    if not visible_projects(user).filter(pk=project.pk).exists():
        raise PermissionDenied
    messages = ProjectMessage.objects.filter(project=project).select_related("author")
    if user.role == "client":
        messages = messages.filter(audience=ProjectMessage.Audience.SHARED)
    return messages


@transaction.atomic
def post_message(user, project_id, body, audience, request_key):
    if not user.is_active or user.role not in {"client", "editor", "admin"}:
        raise PermissionDenied
    try:
        key = uuid.UUID(str(request_key))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Reload the page and try sending your message again.") from None
    text = body.strip() if isinstance(body, str) else ""
    if not 1 <= len(text) <= 5000:
        raise ValidationError("Enter a message of 1 to 5,000 characters.")
    if audience not in ProjectMessage.Audience.values:
        raise ValidationError("Choose a valid message audience.")
    if user.role == "client" and audience != ProjectMessage.Audience.SHARED:
        raise PermissionDenied
    project_for(user, project_id)
    project = Project.objects.select_for_update().get(pk=project_id)
    if not visible_projects(user).filter(pk=project.pk).exists():
        raise PermissionDenied
    existing = ProjectMessage.objects.filter(request_key=key).first()
    if existing:
        if (existing.project_id, existing.author_id, existing.audience, existing.body) == (
            project.id,
            user.id,
            audience,
            text,
        ):
            return existing
        raise ValidationError("This message request was already used. Reload and try again.")
    try:
        with transaction.atomic():
            message = ProjectMessage.objects.create(
                project=project, author=user, audience=audience, body=text, request_key=key
            )
    except IntegrityError:
        raise ValidationError("This message request was already processed. Reload the project.") from None
    assignment = (
        EditorAssignment.objects.filter(project=project, ended_at__isnull=True)
        .select_related("editor__user")
        .first()
    )
    recipients = list(User.objects.filter(role="admin", is_active=True))
    if assignment and assignment.editor.approved and assignment.editor.user.is_active:
        recipients.append(assignment.editor.user)
    if audience == ProjectMessage.Audience.SHARED:
        recipients.append(project.client.user)
    for recipient in recipients:
        if recipient.pk != user.pk:
            notify(
                recipient,
                project,
                f"message:{message.pk}:recipient:{recipient.pk}",
                "New project message." if audience == "shared" else "New internal project note.",
            )
    audit(
        user,
        "project.message_posted",
        message.pk,
        {"project": str(project.pk), "audience": audience},
    )
    return message
