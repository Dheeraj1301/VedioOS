from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.models import Project
from core.permissions import role_required

from .assignment_forms import (
    AdminAvailabilityOverrideForm,
    AssignmentPolicyForm,
    ComplexityForm,
    EditorOperationsForm,
    ManualAssignmentForm,
)
from .assignments import (
    TERMINAL,
    assign_next,
    classify_and_allocate,
    configure_editor,
    editor_roster,
    eligibility,
    manual_assign,
    open_workload,
    process_queue,
    save_policy,
)
from .availability import availability_state, set_availability_override
from .models import (
    AssignmentPolicy,
    AssignmentQueue,
    Editor,
    EditorAssignment,
    ProjectComplexity,
    RoundRobinState,
)


@role_required("admin")
def assignments(request):
    mode = request.GET.get("status", "review")
    projects = (
        Project.objects.filter(
            archived_at__isnull=True,
            order__payment_status="confirmed",
            payment_completed_at__isnull=False,
        )
        .exclude(status__in=TERMINAL)
        .select_related("client__user", "order", "projectcomplexity__proficiency", "assignmentqueue")
    )
    if mode == "review":
        projects = projects.filter(
            Q(projectcomplexity__isnull=True) | Q(projectcomplexity__proficiency__isnull=True)
        )
    elif mode == "waiting":
        projects = projects.filter(assignmentqueue__status="waiting")
    elif mode == "assigned":
        projects = projects.filter(assignments__ended_at__isnull=True, assignments__isnull=False)
    return render(
        request,
        "assignments/overview.html",
        {
            "title": "Assignments",
            "projects": projects.distinct(),
            "mode": mode,
            "policy": AssignmentPolicy.objects.filter(pk=1).first(),
            "rotations": RoundRobinState.objects.select_related("proficiency", "last_editor__user"),
        },
    )


@role_required("admin")
def assignment_policy(request):
    policy = AssignmentPolicy.objects.get(pk=1)
    form = AssignmentPolicyForm(request.POST or None, instance=policy)
    if request.method == "POST" and form.is_valid():
        try:
            save_policy(request.user, request.POST)
            messages.success(request, "Assignment policy saved. Rotation positions are preserved.")
            return redirect("assignments")
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(
        request,
        "assignments/form.html",
        {
            "title": "Assignment policy",
            "form": form,
            "description": "Choose operating rules explicitly. Automatic allocation runs when you process the queue or run the worker command; it does not start a background service.",
        },
    )


@role_required("admin")
def editor_detail(request, editor_id):
    editor = get_object_or_404(
        Editor.objects.filter(user__auth_deleted_at__isnull=True).select_related(
            "user", "proficiency", "approved_by"
        ),
        pk=editor_id,
    )
    availability = availability_state(editor)
    return render(
        request,
        "assignments/editor_detail.html",
        {
            "title": editor.user.name,
            "editor": editor,
            "availability": availability,
            "active_count": availability["active_count"],
        },
    )


@require_POST
@role_required("admin")
def editor_availability_override(request, editor_id):
    editor = get_object_or_404(
        Editor.objects.filter(user__auth_deleted_at__isnull=True), pk=editor_id
    )
    form = AdminAvailabilityOverrideForm(request.POST)
    if form.is_valid():
        try:
            set_availability_override(
                request.user,
                editor.pk,
                form.cleaned_data["status"],
                form.cleaned_data["reason"],
            )
            if form.cleaned_data["status"] == Editor.AvailabilityOverride.AUTOMATIC:
                try:
                    process_queue(request.user)
                except ValidationError:
                    pass
            messages.success(request, "Editor availability status updated.")
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
    else:
        messages.error(request, "Choose a status and provide a reason.")
    return redirect(f"/admin/editors/#editor-{editor.pk}")


@role_required("admin")
def editor_operations(request, editor_id):
    editor = get_object_or_404(
        Editor.objects.filter(user__auth_deleted_at__isnull=True).select_related("user"),
        pk=editor_id,
    )
    form = EditorOperationsForm(
        request.POST or None,
        initial={
            "approved": editor.approved,
            "proficiency": editor.proficiency_id,
            "workload_capacity": editor.workload_capacity,
        },
    )
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            configure_editor(
                request.user,
                editor.id,
                approved=data["approved"],
                proficiency=data["proficiency"].pk if data["proficiency"] else None,
                capacity=data["workload_capacity"],
                reason=data["reason"],
            )
            messages.success(request, "Editor eligibility and capacity updated.")
            return redirect("/admin/editors/")
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(
        request,
        "assignments/form.html",
        {
            "title": f"Manage {editor.user.name}",
            "form": form,
            "description": f"Current active projects: {open_workload(editor)}. Availability is calculated automatically; existing assignments remain until reassigned or completed.",
        },
    )


@role_required("admin")
def assignment_detail(request, project_id):
    project = get_object_or_404(
        Project.objects.filter(archived_at__isnull=True).select_related("order", "client__user"),
        pk=project_id,
    )
    complexity = ProjectComplexity.objects.filter(project=project).first()
    current = (
        EditorAssignment.objects.filter(project=project, ended_at__isnull=True)
        .select_related("editor__user")
        .first()
    )
    assessment = ComplexityForm(
        prefix="assessment",
        initial={
            "expected_revision": complexity.revision if complexity else 0,
            "proficiency": complexity.proficiency_id if complexity else None,
        },
    )
    manual = ManualAssignmentForm(
        prefix="manual", initial={"expected_assignment": current.id if current else None}
    )
    action = request.POST.get("action")
    if request.method == "POST":
        try:
            if action == "classify":
                assessment = ComplexityForm(request.POST, prefix="assessment")
                if assessment.is_valid():
                    data = assessment.cleaned_data
                    _, assignment = classify_and_allocate(
                        request.user,
                        project.id,
                        data["proficiency"].pk,
                        data["reason"],
                        data["expected_revision"],
                    )
                    if assignment:
                        messages.success(
                            request,
                            "Complexity reviewed and the next eligible editor was assigned automatically.",
                        )
                    elif AssignmentPolicy.objects.get(pk=1).automatic_enabled:
                        messages.success(
                            request,
                            "Complexity reviewed. The project remains queued; see the waiting reason below.",
                        )
                    else:
                        messages.success(
                            request,
                            "Complexity reviewed. Unassigned paid work is queued.",
                        )
                    return redirect("assignment_detail", project_id=project.id)
            elif action == "manual":
                manual = ManualAssignmentForm(request.POST, prefix="manual")
                if manual.is_valid():
                    data = manual.cleaned_data
                    manual_assign(
                        request.user,
                        project.id,
                        data["editor"].pk,
                        data["reason"],
                        data["expected_assignment"],
                    )
                    messages.success(
                        request, "Assignment saved. The former editor can no longer request project access."
                    )
                    return redirect("assignment_detail", project_id=project.id)
            elif action == "automatic":
                result = assign_next(project.id, request.user)
                messages.success(
                    request,
                    "Editor assigned." if result else "Project remains queued; see the waiting reason below.",
                )
                return redirect("assignment_detail", project_id=project.id)
            else:
                messages.error(request, "Choose a valid operation.")
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
    candidates = []
    if complexity and complexity.proficiency_id:
        for editor in (
            editor_roster()
            .filter(proficiency_id=complexity.proficiency_id)
            .select_related("user")
        ):
            candidates.append(
                {
                    "editor": editor,
                    "count": open_workload(editor),
                    "problem": eligibility(editor, complexity.proficiency_id),
                }
            )
    return render(
        request,
        "assignments/detail.html",
        {
            "title": "Project assignment",
            "project": project,
            "complexity": complexity,
            "current": current,
            "assessment": assessment,
            "manual": manual,
            "policy": AssignmentPolicy.objects.get(pk=1),
            "candidates": candidates,
            "queue": AssignmentQueue.objects.filter(project=project).first(),
            "history": project.assignments.select_related("editor__user", "assigned_by").order_by(
                "-created_at"
            ),
        },
    )


@require_POST
@role_required("admin")
def run_queue(request):
    try:
        assigned, waiting = process_queue(request.user)
        messages.success(
            request, f"Processed queue: {assigned} assigned; {waiting} waiting. Up to 50 projects per run."
        )
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    return redirect("assignments")
