import uuid

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from core.permissions import role_required, visible_projects

from .models import SupportRequest
from .support import (
    change_support_status,
    create_support_request,
    post_support_message,
    support_request_for,
    visible_support_messages,
)


@require_GET
@role_required("client")
def client_support(request):
    return render(
        request,
        "operations/support_list.html",
        {
            "title": "Support",
            "support_requests": SupportRequest.objects.filter(client__user=request.user),
            "categories": SupportRequest.Category.choices,
            "projects": visible_projects(request.user),
            "request_key": uuid.uuid4(),
            "is_admin": False,
        },
    )


@require_POST
@role_required("client")
def create_support(request):
    if set(request.POST) - {
        "csrfmiddlewaretoken",
        "subject",
        "category",
        "body",
        "project",
        "request_key",
    }:
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied
    try:
        support_request = create_support_request(
            request.user,
            request.POST.get("subject"),
            request.POST.get("category"),
            request.POST.get("body"),
            request.POST.get("project"),
            request.POST.get("request_key"),
        )
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("client_support")
    messages.success(request, "Support request opened.")
    return redirect("support_detail", request_id=support_request.pk)


@require_GET
@role_required("admin")
def admin_support(request):
    status = request.GET.get("status", "open")
    rows = SupportRequest.objects.select_related("client__user", "project")
    if status in SupportRequest.Status.values:
        rows = rows.filter(status=status)
    else:
        status = "all"
    return render(
        request,
        "operations/support_list.html",
        {
            "title": "Client support",
            "support_requests": rows,
            "statuses": SupportRequest.Status.choices,
            "selected_status": status,
            "is_admin": True,
        },
    )


@require_GET
@role_required("client", "admin")
def support_detail(request, request_id):
    support_request = support_request_for(request.user, request_id)
    return render(
        request,
        "operations/support_detail.html",
        {
            "title": support_request.subject,
            "support_request": support_request,
            "support_messages": visible_support_messages(request.user, support_request),
            "statuses": SupportRequest.Status.choices,
            "shared_key": uuid.uuid4(),
            "internal_key": uuid.uuid4(),
        },
    )


@require_POST
@role_required("client", "admin")
def support_message(request, request_id):
    if set(request.POST) - {"csrfmiddlewaretoken", "body", "audience", "request_key"}:
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied
    try:
        post_support_message(
            request.user,
            request_id,
            request.POST.get("body"),
            request.POST.get("audience"),
            request.POST.get("request_key"),
        )
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, "Support message saved.")
    return redirect("support_detail", request_id=request_id)


@require_POST
@role_required("admin")
def support_status(request, request_id):
    if set(request.POST) - {"csrfmiddlewaretoken", "status"}:
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied
    try:
        change_support_status(request.user, request_id, request.POST.get("status"))
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, "Support status updated.")
    return redirect("support_detail", request_id=request_id)
