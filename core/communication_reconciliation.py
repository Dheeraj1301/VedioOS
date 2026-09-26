"""Read-only project-conversation and client-support reconciliation."""

from operations.models import ProjectMessage, SupportMessage, SupportRequest


def _safe_text(value, maximum):
    return isinstance(value, str) and value == value.strip() and 1 <= len(value) <= maximum


def _project_message_findings():
    invalid_content = 0
    invalid_author_or_audience = 0
    rows = ProjectMessage.objects.select_related("project__client__user", "author")
    for message in rows.iterator(chunk_size=100):
        if (
            message.audience not in ProjectMessage.Audience.values
            or not _safe_text(message.body, 5000)
            or not message.request_key
        ):
            invalid_content += 1
        author = message.author
        valid_author = False
        if author.role == "client":
            valid_author = bool(
                author.pk == message.project.client.user_id
                and message.audience == ProjectMessage.Audience.SHARED
            )
        elif author.role == "editor":
            valid_author = message.project.assignments.filter(editor__user=author).exists()
        elif author.role == "admin":
            valid_author = True
        if not valid_author:
            invalid_author_or_audience += 1
    return invalid_content, invalid_author_or_audience


def _support_request_findings():
    invalid_record = 0
    missing_or_invalid_opening = 0
    rows = SupportRequest.objects.select_related("client__user", "project")
    for support_request in rows.iterator(chunk_size=100):
        if (
            not _safe_text(support_request.subject, 160)
            or support_request.category not in SupportRequest.Category.values
            or support_request.status not in SupportRequest.Status.values
            or not support_request.request_key
            or support_request.project_id is not None
            and support_request.project.client_id != support_request.client_id
        ):
            invalid_record += 1
        first = support_request.messages.order_by("created_at", "id").first()
        if (
            first is None
            or first.author_id != support_request.client.user_id
            or first.audience != SupportMessage.Audience.SHARED
            or first.request_key != support_request.request_key
        ):
            missing_or_invalid_opening += 1
    return invalid_record, missing_or_invalid_opening


def _support_message_findings():
    invalid_content = 0
    invalid_author_or_audience = 0
    rows = SupportMessage.objects.select_related("support_request__client__user", "author")
    for message in rows.iterator(chunk_size=100):
        if (
            message.audience not in SupportMessage.Audience.values
            or not _safe_text(message.body, 5000)
            or not message.request_key
        ):
            invalid_content += 1
        author = message.author
        if author.role == "client":
            valid_author = bool(
                author.pk == message.support_request.client.user_id
                and message.audience == SupportMessage.Audience.SHARED
            )
        else:
            valid_author = author.role == "admin"
        if not valid_author:
            invalid_author_or_audience += 1
    return invalid_content, invalid_author_or_audience


def communication_reconciliation_report():
    project_content, project_author = _project_message_findings()
    support_record, support_opening = _support_request_findings()
    support_content, support_author = _support_message_findings()
    critical = {
        "invalid_project_message_content": project_content,
        "invalid_project_message_author_or_audience": project_author,
        "invalid_support_request": support_record,
        "missing_or_invalid_support_opening_message": support_opening,
        "invalid_support_message_content": support_content,
        "invalid_support_message_author_or_audience": support_author,
    }
    warnings = {
        "open_support_requests": SupportRequest.objects.filter(
            status__in=[SupportRequest.Status.OPEN, SupportRequest.Status.IN_PROGRESS]
        ).count(),
        "resolved_not_closed_support_requests": SupportRequest.objects.filter(
            status=SupportRequest.Status.RESOLVED
        ).count(),
    }
    critical_count = sum(critical.values())
    return {
        "status": "pass" if critical_count == 0 else "fail",
        "code": "communications_consistent"
        if critical_count == 0
        else "communication_reconciliation_failed",
        "project_message_count": ProjectMessage.objects.count(),
        "support_request_count": SupportRequest.objects.count(),
        "support_message_count": SupportMessage.objects.count(),
        "critical": critical,
        "warnings": warnings,
        "critical_count": critical_count,
        "warning_count": sum(warnings.values()),
    }
