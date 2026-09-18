"""Transactional assignment boundary.

Lock order: policy → order → project → editor/rotation. A single small policy row
serializes allocation and editor eligibility changes across proficiency groups.
No network I/O occurs under this lock. PostgreSQL is required for concurrency.
"""

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from core.models import Order, Project
from core.views import audit

from .assignment_forms import AssignmentPolicyForm
from .calls import notify
from .models import (
    AssignmentPolicy,
    AssignmentQueue,
    Editor,
    EditorAssignment,
    EditorAvailability,
    EditorProficiency,
    ProjectComplexity,
    RoundRobinState,
)

TERMINAL = ["completed", "cancelled"]


def admin_only(user):
    if not user or not user.is_active or user.role != "admin":
        raise PermissionDenied


def locked_policy():
    # The migration seeds this row. No request-time schema/config creation.
    return AssignmentPolicy.objects.select_for_update().get(pk=1)


def validate_policy(policy, automatic=False):
    values = {name: getattr(policy, name) for name in AssignmentPolicyForm.Meta.fields}
    if not AssignmentPolicyForm(values, instance=policy).is_valid():
        raise ValidationError("Complete the assignment policy before allocating work.")
    if not (policy.automatic_enabled if automatic else policy.manual_enabled):
        raise ValidationError(
            "Automatic assignment is disabled."
            if automatic
            else "Manual assignment is disabled. Configure the policy first."
        )


def paid_project(project_id):
    order = Order.objects.select_for_update().get(project_id=project_id)
    project = Project.objects.select_for_update().get(pk=project_id)
    payments = order.payments.filter(
        status="confirmed", amount_minor=order.total_minor, currency=order.currency
    )
    if not settings.DEBUG:
        payments = payments.exclude(provider="sandbox")
    if order.payment_status != "confirmed" or not project.payment_completed_at or not payments.exists():
        raise ValidationError("A verified matching payment is required before assignment.")
    if project.status in TERMINAL or project.status == "payment_pending":
        raise ValidationError("This project's current state does not allow assignment.")
    return project


def open_workload(editor):
    if hasattr(editor, "active_count"):
        return editor.active_count
    return (
        EditorAssignment.objects.filter(editor=editor, ended_at__isnull=True)
        .exclude(project__status__in=TERMINAL)
        .count()
    )


def editor_roster():
    return Editor.objects.select_related("user", "proficiency", "availability").annotate(
        active_count=Count(
            "assignments",
            filter=Q(assignments__ended_at__isnull=True) & ~Q(assignments__project__status__in=TERMINAL),
        )
    )


def eligibility(editor, proficiency):
    if not editor.approved or not editor.user.is_active:
        return "Editor is not approved or the account is inactive."
    if editor.proficiency_id != proficiency:
        return "Editor proficiency does not match the project. Review complexity before changing levels."
    availability = getattr(editor, "availability", None)
    if not availability or availability.status != "available":
        return "Editor is not available."
    if not editor.workload_capacity:
        return "Editor capacity has not been configured."
    if open_workload(editor) >= editor.workload_capacity:
        return "Editor is at capacity."
    return ""


@transaction.atomic
def save_policy(user, data):
    admin_only(user)
    policy = locked_policy()
    form = AssignmentPolicyForm(data, instance=policy)
    if not form.is_valid():
        raise ValidationError(form.errors.as_text())
    form.save()
    audit(
        user,
        "assignment.policy_updated",
        policy.pk,
        {name: getattr(policy, name) for name in form.Meta.fields},
    )
    return policy


@transaction.atomic
def configure_editor(user, editor_id, *, approved, proficiency, capacity, status, reason):
    admin_only(user)
    locked_policy()
    editor = Editor.objects.select_for_update().get(pk=editor_id)
    if not reason.strip() or status not in EditorAvailability.Status.values:
        raise ValidationError("Provide a reason and a valid availability status.")
    if capacity is not None and (type(capacity) is not int or not 1 <= capacity <= 1000):
        raise ValidationError("Capacity must be a positive whole number.")
    if approved and not EditorProficiency.objects.filter(pk=proficiency).exists():
        raise ValidationError("Select an approved proficiency level.")
    active = open_workload(editor)
    if active and (not approved or capacity is None or capacity < active):
        raise ValidationError(
            "Reassign open projects before revoking approval or reducing capacity below their count."
        )
    previous = {
        "approved": editor.approved,
        "proficiency": editor.proficiency_id,
        "capacity": editor.workload_capacity,
    }
    editor.approved, editor.proficiency_id, editor.workload_capacity = approved, proficiency, capacity
    editor.approved_by = user if approved else None
    editor.save(update_fields=["approved", "proficiency", "workload_capacity", "approved_by", "updated_at"])
    EditorAvailability.objects.update_or_create(editor=editor, defaults={"status": status})
    audit(
        user,
        "editor.operations_updated",
        editor.id,
        {
            "previous": previous,
            "approved": approved,
            "proficiency": proficiency,
            "capacity": capacity,
            "availability": status,
            "reason": reason,
        },
    )
    return editor


@transaction.atomic
def change_availability(user, status):
    if user.role != "editor" or not user.is_active:
        raise PermissionDenied
    locked_policy()
    if status not in EditorAvailability.Status.values:
        raise ValidationError("Invalid availability.")
    editor = Editor.objects.select_for_update().get(user=user)
    EditorAvailability.objects.update_or_create(editor=editor, defaults={"status": status})
    audit(user, "editor.availability_changed", editor.id, {"status": status})


@transaction.atomic
def approve_proficiency(user, editor_id, level):
    admin_only(user)
    locked_policy()
    editor = Editor.objects.select_for_update().get(pk=editor_id)
    if not EditorProficiency.objects.filter(pk=level).exists():
        raise ValidationError("Invalid proficiency.")
    previous = editor.proficiency_id
    editor.approved, editor.proficiency_id, editor.approved_by = True, level, user
    editor.save(update_fields=["approved", "proficiency", "approved_by", "updated_at"])
    audit(user, "editor.proficiency_approved", editor.id, {"previous": previous, "level": level})
    return editor


@transaction.atomic
def classify(user, project_id, level, reason, expected_revision):
    admin_only(user)
    locked_policy()
    project = paid_project(project_id)
    if not reason.strip() or not EditorProficiency.objects.filter(pk=level).exists():
        raise ValidationError("Select a proficiency and explain the assessment.")
    record = ProjectComplexity.objects.filter(project=project).first()
    if (record.revision if record else 0) != expected_revision:
        raise ValidationError("Another assessment was saved. Reload before changing complexity.")
    previous = record.proficiency_id if record else None
    if not record:
        record = ProjectComplexity(project=project, revision=0)
    record.proficiency_id, record.internal_reason, record.overridden_by = level, reason, user
    record.rule_version = "admin-review-v1"
    record.revision += 1
    record.save()
    current = EditorAssignment.objects.filter(project=project, ended_at__isnull=True).first()
    AssignmentQueue.objects.update_or_create(
        project=project,
        defaults={
            "proficiency_id": level,
            "status": "assigned" if current else "waiting",
            "blocked_reason": "",
        },
    )
    if not current and project.status == "payment_completed":
        project.status = "awaiting_assignment"
        project.save(update_fields=["status", "updated_at"])
    audit(
        user,
        "project.complexity_reviewed",
        project.id,
        {"previous": previous, "level": level, "revision": record.revision, "reason": reason},
    )
    return record


def write_assignment(user, project, editor, policy, reason, current=None, automatic=False):
    now = timezone.now()
    if current:
        current.ended_at = now
        current.save(update_fields=["ended_at", "updated_at"])
    snapshot = {name: getattr(policy, name) for name in AssignmentPolicyForm.Meta.fields}
    complexity = ProjectComplexity.objects.get(project=project)
    snapshot.update(
        {
            "complexity_revision": complexity.revision,
            "proficiency": complexity.proficiency_id,
            "mode": "automatic" if automatic else "manual",
        }
    )
    assignment = EditorAssignment.objects.create(
        project=project, editor=editor, assigned_by=user, reason=reason, policy_snapshot=snapshot
    )
    if automatic or policy.manual_pointer == "advance":
        state, _ = RoundRobinState.objects.get_or_create(proficiency_id=complexity.proficiency_id)
        state.last_editor, state.sequence = editor, state.sequence + 1
        state.save()
    if project.status in ["payment_completed", "awaiting_assignment"]:
        project.status = "editor_assigned"
        project.save(update_fields=["status", "updated_at"])
    AssignmentQueue.objects.update_or_create(
        project=project,
        defaults={"proficiency_id": complexity.proficiency_id, "status": "assigned", "blocked_reason": ""},
    )
    audit(
        user,
        "project.reassigned" if current else "project.assigned",
        project.id,
        {
            "assignment": str(assignment.id),
            "old_editor": str(current.editor_id) if current else None,
            "editor": str(editor.id),
            "reason": reason,
            "mode": snapshot["mode"],
        },
    )
    notify(editor.user, project, f"assignment:{assignment.pk}:editor", "A project has been assigned to you.")
    notify(
        project.client.user,
        project,
        f"assignment:{assignment.pk}:client",
        "An editor has been assigned to your project.",
    )
    return assignment


@transaction.atomic
def manual_assign(user, project_id, editor_id, reason, expected_assignment=None):
    admin_only(user)
    policy = locked_policy()
    validate_policy(policy)
    project = paid_project(project_id)
    complexity = ProjectComplexity.objects.filter(project=project, proficiency__isnull=False).first()
    if not complexity:
        raise ValidationError("Review project complexity before assignment.")
    current = EditorAssignment.objects.filter(project=project, ended_at__isnull=True).first()
    if current and current.editor_id == editor_id:
        return current
    if str(current.id if current else "") != str(expected_assignment or ""):
        raise ValidationError("The assignment changed. Reload and review before reassigning.")
    if not reason.strip():
        raise ValidationError("Explain the assignment or reassignment.")
    editor = Editor.objects.select_for_update().get(pk=editor_id)
    problem = eligibility(editor, complexity.proficiency_id)
    if problem:
        raise ValidationError(problem)
    return write_assignment(user, project, editor, policy, reason, current)


@transaction.atomic
def assign_next(project_id, user=None):
    if user is not None:
        admin_only(user)
    policy = locked_policy()
    validate_policy(policy, automatic=True)
    project = paid_project(project_id)
    current = EditorAssignment.objects.filter(project=project, ended_at__isnull=True).first()
    if current:
        return current
    queue = AssignmentQueue.objects.filter(project=project, status="waiting").first()
    complexity = ProjectComplexity.objects.filter(project=project, proficiency__isnull=False).first()
    if not queue or not complexity or queue.proficiency_id != complexity.proficiency_id:
        raise ValidationError("Project needs a current complexity review before queue allocation.")
    state, _ = RoundRobinState.objects.get_or_create(proficiency_id=queue.proficiency_id)
    editors = list(
        editor_roster()
        .filter(approved=True, proficiency_id=queue.proficiency_id, user__is_active=True)
        .order_by("created_at", "id")
    )
    if state.last_editor_id:
        last = state.last_editor
        after = [item for item in editors if (item.created_at, item.id) > (last.created_at, last.id)]
        before = [item for item in editors if (item.created_at, item.id) <= (last.created_at, last.id)]
        editors = after + before
    queue.attempts += 1
    queue.last_attempt_at = timezone.now()
    queue.blocked_reason = "No approved editors in this proficiency group."
    for editor in editors:
        problem = eligibility(editor, queue.proficiency_id)
        if not problem:
            queue.save(update_fields=["attempts", "last_attempt_at", "updated_at"])
            return write_assignment(user, project, editor, policy, "Round-robin allocation", automatic=True)
        queue.blocked_reason = f"Waiting for {editor.user.name}: {problem}"
        if policy.busy_strategy == "wait":
            break
    if editors and policy.busy_strategy == "skip":
        queue.blocked_reason = "All approved editors in this group are unavailable or at capacity."
    queue.save(update_fields=["attempts", "last_attempt_at", "blocked_reason", "updated_at"])
    return None


def process_queue(user=None, limit=50):
    if user is not None:
        admin_only(user)
    validate_policy(AssignmentPolicy.objects.get(pk=1), automatic=True)
    ids = list(
        AssignmentQueue.objects.filter(status="waiting")
        .order_by("project__payment_completed_at", "created_at", "id")
        .values_list("project_id", flat=True)[:limit]
    )
    assigned, waiting = 0, 0
    for project_id in ids:
        try:
            result = assign_next(project_id, user)
        except ValidationError:
            waiting += 1
        else:
            assigned += bool(result)
            waiting += not bool(result)
    return assigned, waiting
