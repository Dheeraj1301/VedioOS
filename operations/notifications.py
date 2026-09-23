"""Durable external-notification delivery. In-app notices remain the source of truth."""

from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from core.permissions import visible_projects

from .models import NotificationDelivery


def _eligible(now):
    due = Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now)
    retryable = Q(state__in=["pending", "failed"]) & due
    stale = Q(state="processing", lease_expires_at__lte=now)
    return retryable | stale


@transaction.atomic
def claim_delivery():
    if not settings.NOTIFICATION_EMAIL_ENABLED:
        return None
    now = timezone.now()
    delivery = (
        NotificationDelivery.objects.select_for_update()
        .select_related("notification__recipient", "notification__project")
        .filter(_eligible(now), attempts__lt=settings.NOTIFICATION_DELIVERY_MAX_ATTEMPTS)
        .order_by("created_at", "id")
        .first()
    )
    if not delivery:
        return None
    notice = delivery.notification
    if (
        not notice.recipient.is_active
        or not notice.recipient.email
        or (
            notice.project_id
            and not visible_projects(notice.recipient).filter(pk=notice.project_id).exists()
        )
    ):
        delivery.state = "cancelled"
        delivery.last_error_code = "recipient_ineligible"
        delivery.lease_expires_at = None
        delivery.save(
            update_fields=["state", "last_error_code", "lease_expires_at", "updated_at"]
        )
        return delivery
    delivery.state = "processing"
    delivery.attempts += 1
    delivery.last_attempt_at = now
    delivery.lease_expires_at = now + timedelta(minutes=10)
    delivery.last_error_code = ""
    delivery.save(
        update_fields=[
            "state",
            "attempts",
            "last_attempt_at",
            "lease_expires_at",
            "last_error_code",
            "updated_at",
        ]
    )
    return delivery


def deliver_one():
    delivery = claim_delivery()
    if not delivery or delivery.state == "cancelled":
        return delivery
    notice = delivery.notification
    reference = f"notification-{notice.id}"
    try:
        sent = EmailMessage(
            subject="VedioOS workspace update",
            body=notice.message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[notice.recipient.email],
            headers={"Message-ID": f"<{reference}@vedioos.local>"},
        ).send(fail_silently=False)
        if sent != 1:
            raise RuntimeError("email_backend_did_not_confirm")
    except Exception as exc:
        with transaction.atomic():
            current = NotificationDelivery.objects.select_for_update().get(pk=delivery.pk)
            current.state = (
                "cancelled"
                if current.attempts >= settings.NOTIFICATION_DELIVERY_MAX_ATTEMPTS
                else "failed"
            )
            current.next_attempt_at = timezone.now() + timedelta(
                minutes=min(2**current.attempts, 60)
            )
            current.lease_expires_at = None
            current.last_error_code = type(exc).__name__[:100]
            current.save(
                update_fields=[
                    "state",
                    "next_attempt_at",
                    "lease_expires_at",
                    "last_error_code",
                    "updated_at",
                ]
            )
            return current
    with transaction.atomic():
        current = NotificationDelivery.objects.select_for_update().get(pk=delivery.pk)
        current.state = "sent"
        current.sent_at = timezone.now()
        current.next_attempt_at = None
        current.lease_expires_at = None
        current.provider_reference = reference
        current.save(
            update_fields=[
                "state",
                "sent_at",
                "next_attempt_at",
                "lease_expires_at",
                "provider_reference",
                "updated_at",
            ]
        )
        return current


def dispatch_due(limit=100):
    processed = []
    for _ in range(limit):
        delivery = deliver_one()
        if delivery is None:
            break
        processed.append(delivery)
    return processed


@transaction.atomic
def release_held(limit=100):
    """Explicitly release older held notices after policy/provider activation."""

    if not settings.NOTIFICATION_EMAIL_ENABLED:
        return 0
    ids = list(
        NotificationDelivery.objects.select_for_update()
        .filter(state="held")
        .order_by("created_at", "id")
        .values_list("id", flat=True)[:limit]
    )
    return NotificationDelivery.objects.filter(pk__in=ids, state="held").update(
        state="pending", next_attempt_at=timezone.now()
    )
