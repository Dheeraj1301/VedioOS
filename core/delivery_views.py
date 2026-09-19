import uuid
from datetime import datetime
from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .delivery import transition
from .permissions import role_required, visible_projects
from .views import audit


@require_POST
@role_required("client", "editor")
def delivery_action(request, project_id):
    try:
        if request.POST.get("action") == "accept" and request.POST.get("confirm") != "yes":
            raise ValidationError("Confirm that you accept this version as the completed delivery.")
        transition(
            request.user,
            project_id,
            request.POST.get("action"),
            file_id=request.POST.get("file_id") or None,
            version_id=request.POST.get("version_id") or None,
            note=request.POST.get("note", ""),
            final=request.POST.get("final") == "yes",
        )
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, "Project updated.")
    return redirect(f"{request.user.role}_project", project_id=project_id)


def _notice_cursor(raw):
    if not isinstance(raw, str) or not 1 <= len(raw) <= 100:
        raise Http404("Invalid notification page.")
    try:
        stamp, key = raw.split("|", 1)
        created_at, notice_id = datetime.fromisoformat(stamp), uuid.UUID(key)
    except (TypeError, ValueError):
        raise Http404("Invalid notification page.") from None
    if timezone.is_naive(created_at):
        raise Http404("Invalid notification page.")
    return created_at, notice_id


@require_GET
@role_required("client", "editor", "admin")
def notifications(request):
    from operations.models import Notification

    before = request.GET.get("before")
    notices = (
        Notification.objects.filter(recipient=request.user)
        .filter(Q(project__isnull=True) | Q(project__in=visible_projects(request.user)))
        .select_related("project")
        .order_by("-created_at", "-id")
    )
    if before is not None:
        stamp, notice_id = _notice_cursor(before)
        notices = notices.filter(Q(created_at__lt=stamp) | Q(created_at=stamp, id__lt=notice_id))
    batch = list(notices[:51])
    older_cursor = None
    if len(batch) > 50:
        oldest = batch[49]
        older_cursor = f"{oldest.created_at.isoformat()}|{oldest.id}"
    return render(
        request,
        "notifications.html",
        {
            "title": "Notifications",
            "notices": batch[:50],
            "older_notice_cursor": older_cursor,
            "current_notice_cursor": before,
        },
    )


@require_POST
@role_required("client", "editor", "admin")
def mark_notification_read(request, notice_id):
    from operations.models import Notification

    before = request.POST.get("before")
    if before is not None:
        _notice_cursor(before)
    with transaction.atomic():
        notice = get_object_or_404(
            Notification.objects.select_for_update()
            .filter(recipient=request.user)
            .filter(Q(project__isnull=True) | Q(project__in=visible_projects(request.user))),
            pk=notice_id,
        )
        if notice.read_at is None:
            notice.read_at = timezone.now()
            notice.save(update_fields=["read_at", "updated_at"])
            audit(
                request.user,
                "notification.read",
                notice.pk,
                {"project": str(notice.project_id) if notice.project_id else None},
            )
    if before:
        return redirect(f"{reverse('notifications')}?{urlencode({'before': before})}")
    return redirect("notifications")
