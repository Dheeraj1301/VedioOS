from datetime import datetime
from datetime import timezone as datetime_timezone

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Exists, OuterRef
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.models import Client, Order
from core.permissions import role_required, visible_projects

from .assignments import approve_proficiency, change_availability, editor_roster, open_workload
from .calls import complete_call, schedule_call
from .forms import AvailabilityForm
from .models import CallRequest, Editor, EditorAssignment, EditorProficiency


def editor_register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    messages.info(request, "Editor accounts are issued by an administrator. Sign in with your editor ID.")
    return redirect("login")


@role_required("editor")
def editor_dashboard(request):
    return render(
        request,
        "operations/editor_dashboard.html",
        {
            "title": "Assigned projects",
            "editor": request.user.editor_profile,
            "active_count": open_workload(request.user.editor_profile),
            "projects": visible_projects(request.user),
        },
    )


@role_required("editor")
def editor_page(request, page):
    editor = request.user.editor_profile
    if page == "calls":
        return render(
            request,
            "operations/editor_calls.html",
            {
                "title": "Consultations",
                "calls": CallRequest.objects.filter(editor=editor)
                .select_related("project")
                .order_by("-scheduled_at"),
            },
        )
    if page == "revisions":
        return render(
            request,
            "projects.html",
            {
                "title": "Requested revisions",
                "projects": visible_projects(request.user).filter(
                    status__in=["revision_requested", "revision_in_progress"]
                ),
            },
        )
    if page == "projects":
        return render(
            request, "projects.html", {"title": "Project details", "projects": visible_projects(request.user)}
        )
    if page == "availability":
        form = AvailabilityForm(request.POST or None, instance=editor.availability)
        if request.method == "POST":
            if set(request.POST) - {"csrfmiddlewaretoken", "status"}:
                raise PermissionDenied
            if form.is_valid():
                change_availability(request.user, form.cleaned_data["status"])
                messages.success(
                    request, "Availability updated. Approval is still required before assignment."
                )
                return redirect("/editor/availability/")
        return render(request, "operations/availability.html", {"title": "Availability", "form": form})
    titles = {
        "revisions": (
            "Revisions",
            "Revision requests will appear here when an assigned project is reviewed.",
        ),
    }
    if page not in titles:
        from django.http import Http404

        raise Http404
    title, description = titles[page]
    return render(request, "operations/skeleton.html", {"title": title, "description": description})


@role_required("admin")
def admin_dashboard(request):
    projects = visible_projects(request.user)
    paid = projects.filter(order__payment_status="confirmed")
    unassigned = (
        paid.annotate(
            has_editor=Exists(EditorAssignment.objects.filter(project=OuterRef("pk"), ended_at__isnull=True))
        )
        .filter(has_editor=False)
        .exclude(status__in=["completed", "cancelled"])
    )
    return render(
        request,
        "operations/admin_dashboard.html",
        {
            "title": "Overview",
            "project_count": projects.count(),
            "unassigned_count": unassigned.count(),
            "review_count": paid.filter(status="awaiting_review").count(),
            "revision_count": paid.filter(status__in=["revision_requested", "revision_in_progress"]).count(),
            "overdue_count": paid.filter(expected_delivery_at__lt=timezone.now())
            .exclude(status__in=["completed", "cancelled"])
            .count(),
            "call_count": CallRequest.objects.filter(status="requested").count(),
            "editor_count": Editor.objects.count(),
            "pending_count": Editor.objects.filter(approved=False).count(),
            "projects": visible_projects(request.user)[:5],
        },
    )


@role_required("admin")
def admin_page(request, page):
    if page == "projects":
        queue = request.GET.get("queue", "all")
        projects = visible_projects(request.user)
        if queue == "unassigned":
            projects = (
                projects.filter(order__payment_status="confirmed")
                .annotate(
                    has_editor=Exists(
                        EditorAssignment.objects.filter(project=OuterRef("pk"), ended_at__isnull=True)
                    )
                )
                .filter(has_editor=False)
                .exclude(status__in=["completed", "cancelled"])
            )
        elif queue == "active":
            projects = projects.filter(status__in=["editor_assigned", "editing"])
        elif queue == "review":
            projects = projects.filter(status="awaiting_review")
        elif queue == "revision":
            projects = projects.filter(status__in=["revision_requested", "revision_in_progress"])
        elif queue == "completed":
            projects = projects.filter(status="completed")
        else:
            queue = "all"
        return render(
            request, "projects.html", {"title": "Projects", "projects": projects, "admin_queue": queue}
        )
    if page == "calls":
        return render(
            request,
            "operations/calls.html",
            {
                "title": "Consultations",
                "calls": CallRequest.objects.select_related(
                    "project", "editor__user", "requested_by"
                ).order_by("status", "scheduled_at", "created_at"),
                "editors": Editor.objects.filter(approved=True, user__is_active=True)
                .select_related("user")
                .order_by("user__name"),
            },
        )
    if page == "editors":
        return render(
            request,
            "operations/editors.html",
            {
                "title": "Editors",
                "editors": editor_roster(),
                "levels": EditorProficiency.objects.all(),
            },
        )
    if page == "clients":
        return render(
            request,
            "operations/clients.html",
            {"title": "Clients", "clients": Client.objects.select_related("user")},
        )
    if page == "orders":
        orders = Order.objects.select_related("project")
        payment_filter = request.GET.get("payment", "all")
        if payment_filter == "paid":
            orders = orders.filter(payment_status="confirmed")
        elif payment_filter == "unpaid":
            orders = orders.exclude(payment_status="confirmed")
        return render(
            request,
            "operations/orders.html",
            {"title": "Orders", "orders": orders.order_by("-created_at"), "payment_filter": payment_filter},
        )
    if page == "pricing":
        return redirect("pricing")
    descriptions = {
        "assignments": "Assignment tools will be enabled after the Day 1 foundation checks pass.",
        "analytics": "Business analytics will follow the confirmed-payment and delivery workflows.",
    }
    if page not in descriptions:
        from django.http import Http404

        raise Http404
    return render(
        request, "operations/skeleton.html", {"title": page.title(), "description": descriptions[page]}
    )


@require_POST
@role_required("admin")
def call_action(request, call_id):
    try:
        action = request.POST.get("action")
        if action == "schedule":
            raw = request.POST.get("scheduled_at", "")
            try:
                when = datetime.fromisoformat(raw)
                if when.tzinfo is None:
                    when = when.replace(tzinfo=datetime_timezone.utc)
            except ValueError:
                raise ValidationError("Enter a valid UTC date and time.") from None
            schedule_call(request.user, call_id, request.POST.get("editor"), when)
            messages.success(request, "Consultation scheduled. The client and editor were notified.")
        elif action == "complete":
            complete_call(request.user, call_id)
            messages.success(request, "Consultation marked complete.")
        else:
            raise ValidationError("Unknown consultation action.")
    except (ValidationError, CallRequest.DoesNotExist) as exc:
        messages.error(
            request, " ".join(exc.messages) if isinstance(exc, ValidationError) else "Consultation not found."
        )
    return redirect("/admin/calls/")


@require_POST
@role_required("admin")
def approve_editor(request, editor_id):
    editor = get_object_or_404(Editor, pk=editor_id)
    level = get_object_or_404(EditorProficiency, pk=request.POST.get("proficiency"))
    approve_proficiency(request.user, editor.id, level.pk)
    messages.success(request, f"{editor.user.name} approved as {level.get_level_display()}.")
    return redirect("/admin/editors/")
