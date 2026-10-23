import uuid

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import OuterRef, Subquery
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from operations.messages import message_page, messaging_enabled, post_message
from operations.models import ProjectMessage

from .models import Project
from .permissions import project_for, role_required, visible_projects


def _is_phone_number_restriction(error):
    return any(item.code == "restricted_phone_number" for item in error.error_list)


def _communication_projects(user, *, exclude_cancelled=False):
    latest_shared = ProjectMessage.objects.filter(
        project_id=OuterRef("pk"), audience=ProjectMessage.Audience.SHARED
    ).order_by("-created_at", "-id")
    projects = visible_projects(user)
    if exclude_cancelled:
        projects = projects.exclude(status=Project.Status.CANCELLED)
    return list(
        projects
        .annotate(
            latest_message=Subquery(latest_shared.values("body")[:1]),
            latest_message_at=Subquery(latest_shared.values("created_at")[:1]),
        )
        .order_by("-updated_at", "-created_at")
    )


@require_GET
@role_required("client")
def client_communication(request):
    projects = _communication_projects(request.user)
    closed = {Project.Status.COMPLETED, Project.Status.CANCELLED}
    return render(
        request,
        "client/communication_list.html",
        {
            "title": "Project Communication",
            "ongoing_projects": [project for project in projects if project.status not in closed],
            "completed_projects": [project for project in projects if project.status in closed],
        },
    )


@require_GET
@role_required("editor")
def editor_communication(request):
    projects = _communication_projects(request.user, exclude_cancelled=True)
    return render(
        request,
        "editor/communication_list.html",
        {
            "title": "Project Communication",
            "ongoing_projects": [
                project for project in projects if project.status != Project.Status.COMPLETED
            ],
            "completed_projects": [
                project for project in projects if project.status == Project.Status.COMPLETED
            ],
        },
    )


@require_GET
@role_required("client")
def client_project_communication(request, project_id):
    project = project_for(request.user, project_id)
    project_messages, older_cursor = message_page(
        request.user, project, request.GET.get("messages_before")
    )
    return render(
        request,
        "client/project_communication.html",
        {
            "title": f"Communication — {project.title}",
            "project": project,
            "project_messages": project_messages,
            "older_message_cursor": older_cursor,
            "is_older_message_page": bool(request.GET.get("messages_before")),
            "message_request_key": uuid.uuid4(),
            "messaging_enabled": messaging_enabled(project),
        },
    )


@require_GET
@role_required("editor")
def editor_project_communication(request, project_id):
    project = project_for(request.user, project_id)
    project_messages, older_cursor = message_page(
        request.user,
        project,
        request.GET.get("messages_before"),
        shared_only=True,
    )
    return render(
        request,
        "editor/project_communication.html",
        {
            "title": f"Communication - {project.title}",
            "project": project,
            "project_messages": project_messages,
            "older_message_cursor": older_cursor,
            "is_older_message_page": bool(request.GET.get("messages_before")),
            "message_request_key": uuid.uuid4(),
            "messaging_enabled": messaging_enabled(project),
        },
    )


@require_POST
@role_required("editor")
def editor_message_post(request, project_id):
    try:
        post_message(
            request.user,
            project_id,
            request.POST.get("body"),
            ProjectMessage.Audience.SHARED,
            request.POST.get("request_key"),
        )
    except ValidationError as exc:
        if _is_phone_number_restriction(exc):
            return HttpResponseBadRequest(" ".join(exc.messages), content_type="text/plain")
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, "Reply saved.")
    return redirect("editor_project_communication", project_id=project_id)


@require_POST
@role_required("client", "editor", "admin")
def message_post(request, project_id):
    try:
        post_message(
            request.user,
            project_id,
            request.POST.get("body"),
            request.POST.get("audience"),
            request.POST.get("request_key"),
        )
    except ValidationError as exc:
        if _is_phone_number_restriction(exc):
            return HttpResponseBadRequest(" ".join(exc.messages), content_type="text/plain")
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, "Message saved.")
    if request.user.role == "client":
        return redirect("client_project_communication", project_id=project_id)
    return redirect(f"{request.user.role}_project", project_id=project_id)
