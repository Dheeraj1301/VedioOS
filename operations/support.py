"""Private client-support workflow and authorization boundary."""

import uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from core.models import Project, User
from core.views import audit

from .calls import notify
from .models import SupportMessage, SupportRequest


def support_request_for(user, request_id, *, lock=False):
    rows = SupportRequest.objects.select_related("client__user", "project")
    if lock:
        rows = rows.select_for_update()
    if user.role == "client":
        rows = rows.filter(client__user=user)
    elif user.role != "admin":
        raise PermissionDenied
    try:
        return rows.get(pk=request_id)
    except (SupportRequest.DoesNotExist, ValueError, TypeError):
        from django.http import Http404

        raise Http404("Support request not found.") from None


def visible_support_messages(user, support_request):
    support_request_for(user, support_request.pk)
    rows = support_request.messages.select_related("author")
    return rows.filter(audience="shared") if user.role == "client" else rows


def _key(raw):
    try:
        return uuid.UUID(str(raw))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Reload the page and try again.") from None


def _text(raw, label, limit):
    value = raw.strip() if isinstance(raw, str) else ""
    if not 1 <= len(value) <= limit:
        raise ValidationError(f"Enter {label} of 1 to {limit:,} characters.")
    return value


@transaction.atomic
def create_support_request(user, subject, category, body, project_id, request_key):
    if user.role != "client" or not user.is_active:
        raise PermissionDenied
    key = _key(request_key)
    subject = _text(subject, "a subject", 160)
    body = _text(body, "a message", 5000)
    if category not in SupportRequest.Category.values:
        raise ValidationError("Choose a valid support category.")
    project = None
    if project_id:
        try:
            project = Project.objects.get(pk=project_id, client=user.client_profile)
        except (Project.DoesNotExist, ValueError, TypeError):
            raise PermissionDenied from None
    existing = SupportRequest.objects.filter(request_key=key).first()
    if existing:
        first_message = existing.messages.order_by("created_at", "id").first()
        if (
            existing.client_id,
            existing.project_id,
            existing.subject,
            existing.category,
            first_message.author_id if first_message else None,
            first_message.body if first_message else None,
        ) == (user.client_profile.id, project.pk if project else None, subject, category, user.pk, body):
            return existing
        raise ValidationError("This support request was already used. Reload and try again.")
    try:
        support_request = SupportRequest.objects.create(
            client=user.client_profile,
            project=project,
            subject=subject,
            category=category,
            request_key=key,
        )
        SupportMessage.objects.create(
            support_request=support_request,
            author=user,
            audience=SupportMessage.Audience.SHARED,
            body=body,
            request_key=key,
        )
    except IntegrityError:
        raise ValidationError("This support request was already processed. Reload the page.") from None
    for admin in User.objects.filter(role="admin", is_active=True):
        notify(
            admin,
            project,
            f"support:{support_request.pk}:opened:recipient:{admin.pk}",
            "New client support request.",
        )
    audit(
        user,
        "support.request_opened",
        support_request.pk,
        {"category": category, "project": str(project.pk) if project else None},
    )
    return support_request


@transaction.atomic
def post_support_message(user, request_id, body, audience, request_key):
    key = _key(request_key)
    body = _text(body, "a message", 5000)
    if audience not in SupportMessage.Audience.values:
        raise ValidationError("Choose a valid message audience.")
    support_request = support_request_for(user, request_id, lock=True)
    if user.role == "client":
        if audience != SupportMessage.Audience.SHARED:
            raise PermissionDenied
        if support_request.status in {SupportRequest.Status.RESOLVED, SupportRequest.Status.CLOSED}:
            raise ValidationError("This support request is closed. Open a new request if you need more help.")
    existing = SupportMessage.objects.filter(request_key=key).first()
    if existing:
        if (
            existing.support_request_id,
            existing.author_id,
            existing.audience,
            existing.body,
        ) == (support_request.id, user.id, audience, body):
            return existing
        raise ValidationError("This message request was already used. Reload and try again.")
    try:
        message = SupportMessage.objects.create(
            support_request=support_request,
            author=user,
            audience=audience,
            body=body,
            request_key=key,
        )
    except IntegrityError:
        raise ValidationError("This message was already processed. Reload the page.") from None
    SupportRequest.objects.filter(pk=support_request.pk).update(updated_at=timezone.now())
    if user.role == "client":
        for admin in User.objects.filter(role="admin", is_active=True):
            notify(
                admin,
                support_request.project,
                f"support-message:{message.pk}:recipient:{admin.pk}",
                "New client support message.",
            )
    elif audience == SupportMessage.Audience.SHARED:
        notify(
            support_request.client.user,
            support_request.project,
            f"support-message:{message.pk}:recipient:{support_request.client.user_id}",
            "Your support request has a new reply.",
        )
    audit(
        user,
        "support.message_posted",
        message.pk,
        {"request": str(support_request.pk), "audience": audience},
    )
    return message


@transaction.atomic
def change_support_status(user, request_id, status):
    if user.role != "admin":
        raise PermissionDenied
    if status not in SupportRequest.Status.values:
        raise ValidationError("Choose a valid support status.")
    support_request = support_request_for(user, request_id, lock=True)
    previous = support_request.status
    if previous == status:
        return support_request
    support_request.status = status
    support_request.save(update_fields=["status", "updated_at"])
    notify(
        support_request.client.user,
        support_request.project,
        f"support:{support_request.pk}:status:{status}:at:{support_request.updated_at.isoformat()}",
        f"Your support request is now {support_request.get_status_display().lower()}.",
    )
    audit(
        user,
        "support.status_changed",
        support_request.pk,
        {"before": previous, "after": status},
    )
    return support_request
