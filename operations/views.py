from django.contrib import messages
from django.contrib.auth import login
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.models import Client, Order
from core.permissions import role_required, visible_projects
from core.views import audit, auth_rate_limited

from .assignments import approve_proficiency, change_availability, editor_roster, open_workload
from .forms import AvailabilityForm, EditorRegistrationForm
from .models import Editor, EditorAvailability, EditorCoins, EditorProficiency


def editor_register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    if request.method == "POST" and auth_rate_limited(request):
        return render(
            request,
            "error.html",
            {"message": "Too many attempts. Please try again in 15 minutes."},
            status=429,
        )
    form = EditorRegistrationForm(request.POST or None)
    if request.method == "POST":
        if any(
            key in request.POST
            for key in ["role", "approved", "proficiency", "is_staff", "is_superuser", "approved_by"]
        ):
            raise PermissionDenied
        if form.is_valid():
            try:
                with transaction.atomic():
                    user = form.save(commit=False)
                    user.role = "editor"
                    user.save()
                    fields = [
                        "phone",
                        "experience",
                        "tools",
                        "portfolio",
                        "previous_work",
                        "expertise",
                        "other_information",
                    ]
                    editor = Editor.objects.create(
                        user=user, **{key: form.cleaned_data[key] for key in fields}
                    )
                    EditorAvailability.objects.create(editor=editor, status=form.cleaned_data["availability"])
                    EditorCoins.objects.create(editor=editor)
                    audit(user, "editor.application_submitted", editor.id)
                login(request, user)
                return redirect("editor_dashboard")
            except IntegrityError:
                form.add_error("email", "This account could not be created. Try logging in.")
    return render(
        request,
        "auth.html",
        {
            "form": form,
            "title": "Bring your craft. Make an impact.",
            "subtitle": "Apply to join our human editing team. Our admins review your experience and proficiency.",
            "mode": "editor",
            "button": "Submit application",
        },
    )


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
        "wallet": (
            "Wallet",
            "Earning and redemption rules are being configured. No coin conversion or payouts are active yet.",
        ),
    }
    if page not in titles:
        from django.http import Http404

        raise Http404
    title, description = titles[page]
    return render(request, "operations/skeleton.html", {"title": title, "description": description})


@role_required("admin")
def admin_dashboard(request):
    return render(
        request,
        "operations/admin_dashboard.html",
        {
            "title": "Overview",
            "project_count": visible_projects(request.user).count(),
            "editor_count": Editor.objects.count(),
            "pending_count": Editor.objects.filter(approved=False).count(),
            "projects": visible_projects(request.user)[:5],
        },
    )


@role_required("admin")
def admin_page(request, page):
    if page == "projects":
        return render(
            request, "projects.html", {"title": "Projects", "projects": visible_projects(request.user)}
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
        "calls": "Consultation preferences are saved with project briefs. Scheduling is coming in the consultation workflow.",
        "payouts": "Payouts are not enabled. Coin values and earning rules have not been finalized.",
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
def approve_editor(request, editor_id):
    editor = get_object_or_404(Editor, pk=editor_id)
    level = get_object_or_404(EditorProficiency, pk=request.POST.get("proficiency"))
    approve_proficiency(request.user, editor.id, level.pk)
    messages.success(request, f"{editor.user.name} approved as {level.get_level_display()}.")
    return redirect("/admin/editors/")
