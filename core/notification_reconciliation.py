"""Read-only notification outbox state and eligibility reconciliation."""

import re

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from operations.models import Notification, NotificationDelivery

from .permissions import visible_projects

SAFE_ERROR_CODE = re.compile(r"^[A-Za-z0-9_.:-]{0,100}$")
UNSENT_ACTIVE_STATES = {"pending", "processing", "failed"}


def _unsafe_text_counts():
    unsafe_errors = 0
    unsafe_references = 0
    for error, reference in NotificationDelivery.objects.values_list(
        "last_error_code", "provider_reference"
    ).iterator(chunk_size=100):
        if not SAFE_ERROR_CODE.fullmatch(error or ""):
            unsafe_errors += 1
        rendered_reference = (reference or "").lower()
        if any(fragment in rendered_reference for fragment in ("http://", "https://", "x-amz-")):
            unsafe_references += 1
    return unsafe_errors, unsafe_references


def _ineligible_queued_deliveries():
    count = 0
    deliveries = NotificationDelivery.objects.filter(
        state__in=UNSENT_ACTIVE_STATES
    ).select_related("notification__recipient", "notification__project")
    for delivery in deliveries.iterator(chunk_size=100):
        notice = delivery.notification
        if not notice.recipient.is_active or not notice.recipient.email:
            count += 1
        elif notice.project_id and not visible_projects(notice.recipient).filter(
            pk=notice.project_id
        ).exists():
            count += 1
    return count


def notification_reconciliation_report():
    now = timezone.now()
    unsafe_errors, unsafe_references = _unsafe_text_counts()
    valid_states = {choice for choice, _ in NotificationDelivery.State.choices}
    valid_channels = {choice for choice, _ in NotificationDelivery._meta.get_field("channel").choices}
    critical = {
        "notices_missing_delivery": Notification.objects.filter(delivery__isnull=True).count(),
        "unknown_states": NotificationDelivery.objects.exclude(state__in=valid_states).count(),
        "unknown_channels": NotificationDelivery.objects.exclude(channel__in=valid_channels).count(),
        "held_state_metadata": NotificationDelivery.objects.filter(state="held")
        .filter(
            Q(attempts__gt=0)
            | Q(next_attempt_at__isnull=False)
            | Q(last_attempt_at__isnull=False)
            | Q(lease_expires_at__isnull=False)
            | Q(sent_at__isnull=False)
            | ~Q(provider_reference="")
            | ~Q(last_error_code="")
        )
        .count(),
        "pending_state_metadata": NotificationDelivery.objects.filter(state="pending")
        .filter(Q(lease_expires_at__isnull=False) | Q(sent_at__isnull=False))
        .count(),
        "processing_state_metadata": NotificationDelivery.objects.filter(state="processing")
        .filter(
            Q(attempts=0)
            | Q(last_attempt_at__isnull=True)
            | Q(lease_expires_at__isnull=True)
            | Q(sent_at__isnull=False)
        )
        .count(),
        "failed_state_metadata": NotificationDelivery.objects.filter(state="failed")
        .filter(
            Q(attempts=0)
            | Q(last_attempt_at__isnull=True)
            | Q(next_attempt_at__isnull=True)
            | Q(lease_expires_at__isnull=False)
            | Q(sent_at__isnull=False)
            | Q(last_error_code="")
        )
        .count(),
        "sent_state_metadata": NotificationDelivery.objects.filter(state="sent")
        .filter(
            Q(attempts=0)
            | Q(sent_at__isnull=True)
            | Q(next_attempt_at__isnull=False)
            | Q(lease_expires_at__isnull=False)
            | Q(provider_reference="")
        )
        .count(),
        "cancelled_state_metadata": NotificationDelivery.objects.filter(state="cancelled")
        .filter(Q(lease_expires_at__isnull=False) | Q(sent_at__isnull=False) | Q(last_error_code=""))
        .count(),
        "retryable_at_or_over_attempt_limit": NotificationDelivery.objects.filter(
            state__in=UNSENT_ACTIVE_STATES,
            attempts__gte=settings.NOTIFICATION_DELIVERY_MAX_ATTEMPTS,
        ).count(),
        "ineligible_queued_deliveries": _ineligible_queued_deliveries(),
        "unsafe_error_codes": unsafe_errors,
        "unsafe_provider_references": unsafe_references,
    }
    state_counts = {
        state: NotificationDelivery.objects.filter(state=state).count()
        for state in sorted(valid_states)
    }
    warnings = {
        "expired_processing_leases": NotificationDelivery.objects.filter(
            state="processing", lease_expires_at__lte=now
        ).count(),
        "held_while_delivery_enabled": (
            state_counts["held"] if settings.NOTIFICATION_EMAIL_ENABLED else 0
        ),
        "active_unsent_while_delivery_disabled": (
            sum(state_counts[state] for state in UNSENT_ACTIVE_STATES)
            if not settings.NOTIFICATION_EMAIL_ENABLED
            else 0
        ),
    }
    critical_count = sum(critical.values())
    return {
        "status": "pass" if critical_count == 0 else "fail",
        "code": "notification_outbox_consistent"
        if critical_count == 0
        else "notification_outbox_failed",
        "notice_count": Notification.objects.count(),
        "delivery_count": NotificationDelivery.objects.count(),
        "states": state_counts,
        "critical": critical,
        "warnings": warnings,
        "critical_count": critical_count,
        "warning_count": sum(warnings.values()),
    }
