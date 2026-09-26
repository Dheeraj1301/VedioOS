"""Audit coverage and detail hygiene checks without exposing event payloads."""

import json

from operations.models import (
    Admin,
    AuditLog,
    CallRequest,
    Editor,
    EditorAssignment,
    ProjectMessage,
    RedemptionRequest,
    SupportMessage,
    SupportRequest,
)

from .models import Client, DeliveryAcceptance, File, Payment, Project, ProjectVersion, RevisionRequest

SYSTEM_ACTIONS = {"deadline.overdue_alerted", "payment.confirmed", "payment.failed"}
FORBIDDEN_DETAIL_KEYS = {
    "body",
    "database_url",
    "email",
    "filename",
    "instructions",
    "message",
    "object_key",
    "password",
    "phone",
    "secret",
    "signed_url",
    "token",
    "url",
}
FORBIDDEN_VALUE_FRAGMENTS = ("http://", "https://", "x-amz-", "database_url=")


def _missing_events(queryset, actions, *, id_field="pk"):
    audited = set(
        AuditLog.objects.filter(action__in=actions).values_list("target_id", flat=True)
    )
    return sum(
        str(target) not in audited
        for target in queryset.values_list(id_field, flat=True).iterator(chunk_size=100)
    )


def _unsafe_detail_rows():
    def detail_keys(value):
        if isinstance(value, dict):
            for key, nested in value.items():
                yield str(key).lower()
                yield from detail_keys(nested)
        elif isinstance(value, list):
            for nested in value:
                yield from detail_keys(nested)

    unsafe = 0
    malformed = 0
    for detail in AuditLog.objects.values_list("detail", flat=True).iterator(chunk_size=100):
        if not isinstance(detail, dict):
            malformed += 1
            continue
        keys = set(detail_keys(detail))
        rendered = json.dumps(detail, sort_keys=True, default=str).lower()
        if keys & FORBIDDEN_DETAIL_KEYS or any(
            fragment in rendered for fragment in FORBIDDEN_VALUE_FRAGMENTS
        ):
            unsafe += 1
    return unsafe, malformed


def audit_reconciliation_report():
    critical = {
        "projects_missing_creation_event": _missing_events(
            Project.objects.all(), {"project.draft_created"}
        ),
        "ready_files_missing_reservation_event": _missing_events(
            File.objects.filter(state="ready"), {"file.upload_reserved"}
        ),
        "ready_files_missing_completion_event": _missing_events(
            File.objects.filter(state="ready"), {"file.upload_completed"}
        ),
        "confirmed_payments_missing_event": _missing_events(
            Payment.objects.filter(status="confirmed"), {"payment.confirmed"}
        ),
        "assignments_missing_event": _missing_events(
            EditorAssignment.objects.all(),
            {"project.assigned", "project.reassigned"},
            id_field="project_id",
        ),
        "versions_missing_submission_event": _missing_events(
            ProjectVersion.objects.all(), {"version.submitted"}
        ),
        "revisions_missing_request_event": _missing_events(
            RevisionRequest.objects.all(), {"revision.requested"}
        ),
        "acceptances_missing_event": _missing_events(
            DeliveryAcceptance.objects.all(), {"delivery.accepted"}
        ),
        "calls_missing_request_event": _missing_events(CallRequest.objects.all(), {"call.requested"}),
        "project_messages_missing_event": _missing_events(
            ProjectMessage.objects.all(), {"project.message_posted"}
        ),
        "support_requests_missing_event": _missing_events(
            SupportRequest.objects.all(), {"support.request_opened"}
        ),
        "support_messages_missing_event": _missing_events(
            SupportMessage.objects.all(), {"support.message_posted"}
        ),
        "redemptions_missing_request_event": _missing_events(
            RedemptionRequest.objects.all(), {"redemption.requested"}
        ),
        "empty_actions": AuditLog.objects.filter(action="").count(),
        "empty_targets": AuditLog.objects.filter(target_id="").count(),
        "unexpected_unattributed_events": AuditLog.objects.filter(actor__isnull=True)
        .exclude(action__in=SYSTEM_ACTIONS)
        .count(),
    }
    unsafe_details, malformed_details = _unsafe_detail_rows()
    critical["unsafe_detail_payloads"] = unsafe_details
    critical["malformed_detail_payloads"] = malformed_details
    warnings = {
        "clients_without_registration_event": _missing_events(
            Client.objects.all(), {"client.registered"}, id_field="user_id"
        ),
        "editors_without_onboarding_event": _missing_events(
            Editor.objects.all(), {"editor.application_submitted", "editor.provisioned"}
        ),
        "admins_without_provision_event": _missing_events(
            Admin.objects.all(), {"admin.provisioned"}, id_field="user_id"
        )
    }
    critical_count = sum(critical.values())
    return {
        "status": "pass" if critical_count == 0 else "fail",
        "code": "audit_history_consistent" if critical_count == 0 else "audit_reconciliation_failed",
        "event_count": AuditLog.objects.count(),
        "critical": critical,
        "warnings": warnings,
        "critical_count": critical_count,
        "warning_count": sum(warnings.values()),
    }
