"""Read-only submitted-version, revision and acceptance reconciliation."""

from .models import DeliveryAcceptance, Project, ProjectVersion, RevisionRequest

REVIEW_STATUSES = {
    Project.Status.REVIEW,
    Project.Status.REVISION_REQUESTED,
    Project.Status.REVISING,
    Project.Status.COMPLETED,
    Project.Status.CANCELLED,
}
REVISION_STATUSES = {"requested", "addressed"}
EARNING_STATUSES = {"pending_policy", "pending_release", "earned"}


def _version_findings():
    invalid_file = 0
    invalid_assignment = 0
    invalid_sequence = 0
    invalid_acceptance_marker = 0
    accepted_versions = set(DeliveryAcceptance.objects.values_list("version_id", flat=True))
    project_numbers = {}
    rows = ProjectVersion.objects.select_related(
        "file", "assignment__editor__user", "project"
    )
    for version in rows.iterator(chunk_size=100):
        project_numbers.setdefault(version.project_id, []).append(version.number)
        file = version.file
        if (
            file.project_id != version.project_id
            or file.state != "ready"
            or not file.storage_version
            or file.category not in {"draft", "final"}
            or file.original_id is not None
        ):
            invalid_file += 1
        assignment = version.assignment
        if (
            assignment is None
            or assignment.project_id != version.project_id
            or file.uploader_id != assignment.editor.user_id
        ):
            invalid_assignment += 1
        if (version.pk in accepted_versions) != (version.accepted_at is not None):
            invalid_acceptance_marker += 1
        if version.project.status not in REVIEW_STATUSES:
            invalid_sequence += 1
    for numbers in project_numbers.values():
        ordered = sorted(numbers)
        if ordered != list(range(1, len(ordered) + 1)):
            invalid_sequence += 1
    return invalid_file, invalid_assignment, invalid_sequence, invalid_acceptance_marker


def _revision_findings():
    invalid_link_or_owner = 0
    invalid_state = 0
    invalid_terms = 0
    project_counts = {}
    rows = RevisionRequest.objects.select_related(
        "project__client__user", "project__order", "version"
    )
    for revision in rows.iterator(chunk_size=100):
        project = revision.project
        project_counts[project.pk] = project_counts.get(project.pk, 0) + 1
        if (
            revision.version.project_id != project.pk
            or revision.requested_by_id != project.client.user_id
            or not revision.instructions.strip()
            or len(revision.instructions) > 5000
        ):
            invalid_link_or_owner += 1
        newer_exists = ProjectVersion.objects.filter(
            project=project, number__gt=revision.version.number
        ).exists()
        if (
            revision.status not in REVISION_STATUSES
            or revision.status == "requested"
            and (newer_exists or project.status not in {Project.Status.REVISION_REQUESTED, Project.Status.REVISING})
            or revision.status == "addressed" and not newer_exists
        ):
            invalid_state += 1
    for project_id, count in project_counts.items():
        terms = Project.objects.select_related("order").get(pk=project_id).order.terms_snapshot
        limit = terms.get("revision_limit") if isinstance(terms, dict) else None
        if (
            not isinstance(terms, dict)
            or terms.get("review_rule") != "latest_request_v1"
            or type(limit) is not int
            or limit < 0
            or count > limit
        ):
            invalid_terms += 1
    return invalid_link_or_owner, invalid_state, invalid_terms


def _acceptance_findings():
    invalid_link_or_owner = 0
    invalid_state = 0
    invalid_terms = 0
    rows = DeliveryAcceptance.objects.select_related(
        "project__client__user", "project__order", "version__assignment", "assignment"
    )
    for acceptance in rows.iterator(chunk_size=100):
        project = acceptance.project
        version = acceptance.version
        latest_number = (
            ProjectVersion.objects.filter(project=project)
            .order_by("-number")
            .values_list("number", flat=True)
            .first()
        )
        if (
            version.project_id != project.pk
            or acceptance.accepted_by_id != project.client.user_id
            or version.assignment_id is None
            or acceptance.assignment_id != version.assignment_id
        ):
            invalid_link_or_owner += 1
        if (
            project.status != Project.Status.COMPLETED
            or version.accepted_at is None
            or version.number != latest_number
            or acceptance.earning_status not in EARNING_STATUSES
        ):
            invalid_state += 1
        if (
            not isinstance(acceptance.terms_snapshot, dict)
            or acceptance.terms_snapshot != project.order.terms_snapshot
        ):
            invalid_terms += 1
    return invalid_link_or_owner, invalid_state, invalid_terms


def _project_state_findings():
    invalid = 0
    projects = Project.objects.filter(
        status__in=[
            Project.Status.REVIEW,
            Project.Status.REVISION_REQUESTED,
            Project.Status.REVISING,
            Project.Status.COMPLETED,
        ]
    )
    for project in projects.iterator(chunk_size=100):
        has_versions = ProjectVersion.objects.filter(project=project).exists()
        requested = RevisionRequest.objects.filter(project=project, status="requested").exists()
        has_acceptance = DeliveryAcceptance.objects.filter(project=project).exists()
        if (
            not has_versions
            or project.status == Project.Status.REVIEW and requested
            or project.status in {Project.Status.REVISION_REQUESTED, Project.Status.REVISING}
            and not requested
            or project.status == Project.Status.COMPLETED and not has_acceptance
        ):
            invalid += 1
    return invalid


def delivery_reconciliation_report():
    version_file, version_assignment, version_sequence, acceptance_marker = _version_findings()
    revision_link, revision_state, revision_terms = _revision_findings()
    acceptance_link, acceptance_state, acceptance_terms = _acceptance_findings()
    critical = {
        "invalid_version_file": version_file,
        "invalid_version_assignment": version_assignment,
        "invalid_version_sequence_or_project_state": version_sequence,
        "invalid_version_acceptance_marker": acceptance_marker,
        "invalid_revision_link_or_owner": revision_link,
        "invalid_revision_state": revision_state,
        "invalid_revision_terms_or_limit": revision_terms,
        "invalid_acceptance_link_or_owner": acceptance_link,
        "invalid_acceptance_state": acceptance_state,
        "invalid_acceptance_terms_snapshot": acceptance_terms,
        "invalid_review_project_state": _project_state_findings(),
    }
    warnings = {
        "projects_awaiting_review": Project.objects.filter(
            status=Project.Status.REVIEW
        ).count(),
        "projects_awaiting_revision_work": Project.objects.filter(
            status__in=[Project.Status.REVISION_REQUESTED, Project.Status.REVISING]
        ).count(),
        "unaccepted_final_candidates": ProjectVersion.objects.filter(
            is_final=True, deliveryacceptance__isnull=True
        ).count(),
    }
    critical_count = sum(critical.values())
    return {
        "status": "pass" if critical_count == 0 else "fail",
        "code": "delivery_consistent" if critical_count == 0 else "delivery_reconciliation_failed",
        "version_count": ProjectVersion.objects.count(),
        "revision_count": RevisionRequest.objects.count(),
        "acceptance_count": DeliveryAcceptance.objects.count(),
        "critical": critical,
        "warnings": warnings,
        "critical_count": critical_count,
        "warning_count": sum(warnings.values()),
    }
