from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .delivery import transition
from .permissions import role_required, visible_projects


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


@role_required("client", "editor", "admin")
def notifications(request):
    from operations.models import Notification

    notices = (
        Notification.objects.filter(recipient=request.user, project__in=visible_projects(request.user))
        .select_related("project")
        .order_by("-created_at")[:100]
    )
    return render(request, "notifications.html", {"title": "Notifications", "notices": notices})
