"""Read-only assignment policy, queue, capacity and rotation reconciliation."""

from django.conf import settings

from operations.assignment_forms import AssignmentPolicyForm
from operations.models import (
    AssignmentPolicy,
    AssignmentQueue,
    Editor,
    EditorAssignment,
    ProjectComplexity,
    RoundRobinState,
)

from .models import Project

TERMINAL_STATUSES = {Project.Status.COMPLETED, Project.Status.CANCELLED}
QUEUE_STATUSES = {"waiting", "assigned"}
PROFICIENCY_LEVELS = {"beginner", "intermediate", "advanced"}


def _funded(project):
    try:
        order = project.order
    except Project.order.RelatedObjectDoesNotExist:
        return False
    payments = order.payments.filter(
        status="confirmed", amount_minor=order.total_minor, currency=order.currency
    )
    if not settings.DEBUG:
        payments = payments.exclude(provider="sandbox")
    return bool(
        order.payment_status == "confirmed"
        and project.payment_completed_at
        and payments.exists()
    )


def _policy_findings(policy):
    if policy is None:
        return 1
    if not (policy.manual_enabled or policy.automatic_enabled):
        return 0
    values = {name: getattr(policy, name) for name in AssignmentPolicyForm.Meta.fields}
    return 0 if AssignmentPolicyForm(values, instance=policy).is_valid() else 1


def _complexity_findings():
    malformed = 0
    for complexity in ProjectComplexity.objects.select_related("overridden_by").iterator(
        chunk_size=100
    ):
        reviewer = complexity.overridden_by
        if (
            not complexity.proficiency_id
            or complexity.revision < 1
            or complexity.rule_version != "admin-review-v1"
            or not complexity.internal_reason.strip()
            or reviewer is None
            or reviewer.role != "admin"
        ):
            malformed += 1
    return malformed


def _queue_findings():
    invalid_state = 0
    funding_or_complexity = 0
    assignment_mismatch = 0
    retry_metadata = 0
    rows = AssignmentQueue.objects.select_related(
        "project__order", "project__projectcomplexity"
    )
    for queue in rows.iterator(chunk_size=100):
        project = queue.project
        current = EditorAssignment.objects.filter(
            project=project, ended_at__isnull=True
        ).exists()
        if queue.status not in QUEUE_STATUSES:
            invalid_state += 1
        try:
            complexity = project.projectcomplexity
        except ProjectComplexity.DoesNotExist:
            complexity = None
        if (
            not _funded(project)
            or project.status in TERMINAL_STATUSES and queue.status == "waiting"
            or complexity is None
            or complexity.proficiency_id != queue.proficiency_id
        ):
            funding_or_complexity += 1
        if (queue.status == "assigned") != current:
            assignment_mismatch += 1
        if (queue.attempts == 0 and queue.last_attempt_at is not None) or (
            queue.attempts > 0 and queue.last_attempt_at is None
        ):
            retry_metadata += 1
    return invalid_state, funding_or_complexity, assignment_mismatch, retry_metadata


def _valid_snapshot(snapshot):
    if not isinstance(snapshot, dict):
        return False
    mode = snapshot.get("mode")
    common = bool(
        snapshot.get("matching") == "exact"
        and snapshot.get("capacity_scope") == "open_assignments"
        and snapshot.get("manual_pointer") in {"preserve", "advance"}
        and snapshot.get("roster_order") == "joined"
        and type(snapshot.get("complexity_revision")) is int
        and snapshot["complexity_revision"] > 0
        and snapshot.get("proficiency") in PROFICIENCY_LEVELS
    )
    if mode == "manual":
        return common and snapshot.get("manual_enabled") is True
    if mode == "automatic":
        return bool(
            common
            and snapshot.get("automatic_enabled") is True
            and snapshot.get("busy_strategy") in {"skip", "wait"}
            and snapshot.get("queue_order") == "paid_at"
        )
    return False


def _assignment_findings():
    invalid_snapshot = 0
    invalid_actor_or_time = 0
    invalid_current_state = 0
    proficiency_drift = 0
    rows = EditorAssignment.objects.select_related(
        "assigned_by",
        "editor__user",
        "project__order",
        "project__projectcomplexity",
        "project__assignmentqueue",
    )
    for assignment in rows.iterator(chunk_size=100):
        if not _valid_snapshot(assignment.policy_snapshot):
            invalid_snapshot += 1
        if (
            not assignment.reason.strip()
            or assignment.ended_at is not None and assignment.ended_at < assignment.created_at
            or assignment.assigned_by is not None and assignment.assigned_by.role != "admin"
        ):
            invalid_actor_or_time += 1
        if assignment.ended_at is not None:
            continue
        project = assignment.project
        if not _funded(project):
            invalid_current_state += 1
        try:
            queue = project.assignmentqueue
            complexity = project.projectcomplexity
        except (AssignmentQueue.DoesNotExist, ProjectComplexity.DoesNotExist):
            invalid_current_state += 1
            continue
        if queue.status != "assigned" or queue.proficiency_id != complexity.proficiency_id:
            invalid_current_state += 1
        if (
            project.status not in TERMINAL_STATUSES
            and (
                not assignment.editor.approved
                or not assignment.editor.user.is_active
                or not assignment.editor.workload_capacity
            )
        ):
            invalid_current_state += 1
        if assignment.editor.proficiency_id != complexity.proficiency_id:
            proficiency_drift += 1
    return invalid_snapshot, invalid_actor_or_time, invalid_current_state, proficiency_drift


def _capacity_findings():
    exceeded = 0
    for editor in Editor.objects.select_related("user").iterator(chunk_size=100):
        open_count = (
            EditorAssignment.objects.filter(editor=editor, ended_at__isnull=True)
            .exclude(project__status__in=TERMINAL_STATUSES)
            .count()
        )
        if open_count and (
            not editor.workload_capacity or open_count > editor.workload_capacity
        ):
            exceeded += 1
    return exceeded


def _missing_queue_findings():
    missing = 0
    rows = ProjectComplexity.objects.select_related("project__order")
    for complexity in rows.iterator(chunk_size=100):
        project = complexity.project
        if (
            project.status not in TERMINAL_STATUSES
            and _funded(project)
            and not AssignmentQueue.objects.filter(project=project).exists()
        ):
            missing += 1
    return missing


def _rotation_findings():
    invalid = 0
    for state in RoundRobinState.objects.iterator(chunk_size=100):
        if (state.sequence == 0 and state.last_editor_id is not None) or (
            state.sequence > 0 and state.last_editor_id is None
        ):
            invalid += 1
    return invalid


def assignment_reconciliation_report():
    policy = AssignmentPolicy.objects.filter(pk=1).first()
    queue_state, queue_context, queue_assignment, queue_retry = _queue_findings()
    assignment_snapshot, assignment_actor, assignment_state, proficiency_drift = (
        _assignment_findings()
    )
    critical = {
        "missing_or_invalid_enabled_policy": _policy_findings(policy),
        "malformed_complexity_reviews": _complexity_findings(),
        "invalid_queue_status": queue_state,
        "queue_funding_or_complexity_mismatch": queue_context,
        "queue_assignment_mismatch": queue_assignment,
        "queue_retry_metadata_mismatch": queue_retry,
        "reviewed_open_projects_missing_queue": _missing_queue_findings(),
        "invalid_assignment_snapshot": assignment_snapshot,
        "invalid_assignment_actor_or_time": assignment_actor,
        "invalid_current_assignment_state": assignment_state,
        "editors_over_capacity": _capacity_findings(),
        "invalid_round_robin_pointer": _rotation_findings(),
    }
    open_funded = Project.objects.exclude(status__in=TERMINAL_STATUSES).filter(
        order__payment_status="confirmed", payment_completed_at__isnull=False
    )
    warnings = {
        "paid_projects_awaiting_complexity": open_funded.filter(
            projectcomplexity__isnull=True, assignments__isnull=True
        ).count(),
        "waiting_queues_with_allocation_disabled": AssignmentQueue.objects.filter(
            status="waiting"
        ).count()
        if not policy or not policy.automatic_enabled
        else 0,
        "current_editor_proficiency_drift": proficiency_drift,
    }
    critical_count = sum(critical.values())
    return {
        "status": "pass" if critical_count == 0 else "fail",
        "code": "assignments_consistent"
        if critical_count == 0
        else "assignment_reconciliation_failed",
        "complexity_count": ProjectComplexity.objects.count(),
        "queue_count": AssignmentQueue.objects.count(),
        "assignment_count": EditorAssignment.objects.count(),
        "rotation_count": RoundRobinState.objects.count(),
        "critical": critical,
        "warnings": warnings,
        "critical_count": critical_count,
        "warning_count": sum(warnings.values()),
    }
