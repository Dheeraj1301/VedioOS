import hashlib
import hmac
import json
import uuid

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from operations.calls import notify, notify_admins

from .models import (
    File,
    Order,
    Project,
    RevisionPlan,
    RevisionPlanAttachment,
    RevisionPlanOrder,
    RevisionPlanPayment,
    RevisionPlanPaymentEvent,
    RevisionRequest,
)
from .payments import _razorpay_request, razorpay_test_enabled
from .permissions import project_for
from .policies import current_policy_snapshot, validate_policy_version
from .views import audit

REVISION_ELIGIBLE_STATUSES = [Project.Status.REVIEW]


def eligible_revision_projects(user):
    eligible_ids = Project.objects.filter(
        client__user=user,
        archived_at__isnull=True,
        payment_completed_at__isnull=False,
        status__in=REVISION_ELIGIBLE_STATUSES,
        versions__isnull=False,
        assignments__ended_at__isnull=True,
    ).values("pk")
    return Project.objects.filter(pk__in=eligible_ids).order_by("title")


@transaction.atomic
def create_revision_order(user, data):
    if user.role != "client" or not isinstance(data, dict):
        raise PermissionDenied
    try:
        request_key = uuid.UUID(str(data.get("request_key")))
        plan_id = uuid.UUID(str(data.get("plan_id")))
        project_id = uuid.UUID(str(data.get("project_id")))
    except (TypeError, ValueError):
        raise ValidationError("Choose a revision plan and eligible project.") from None
    existing = RevisionPlanOrder.objects.filter(request_key=request_key, client__user=user).first()
    if existing:
        return existing
    plan = RevisionPlan.objects.select_for_update().filter(pk=plan_id, active=True).first()
    project = eligible_revision_projects(user).select_for_update().filter(pk=project_id).first()
    if not plan or not project:
        raise ValidationError("Choose an available revision plan and eligible project.")
    if project.status != "awaiting_review" or not project.versions.exists():
        raise ValidationError("This project must have a submitted version awaiting review.")
    assignment = project.assignments.filter(ended_at__isnull=True).first()
    if not assignment:
        raise ValidationError("The original project must have a current editor.")
    song = str(data.get("song_reference", "")).strip()
    changes = str(data.get("changes", "")).strip()
    if not song or len(song) > 500:
        raise ValidationError("Enter a song name or link, or enter NA when there is no change.")
    if not changes or len(changes) > 5000:
        raise ValidationError("Describe the requested changes in 1–5,000 characters.")
    raw_file_ids = data.get("file_ids", [])
    if not isinstance(raw_file_ids, list):
        raise ValidationError("Invalid additional files.")
    if plan.slot != 3 and raw_file_ids:
        raise ValidationError("Additional files are available only with Punaha 3.")
    files = list(
        File.objects.filter(
            pk__in=raw_file_ids,
            project=project,
            uploader=user,
            category="asset",
            state="ready",
            original__isnull=True,
        )
    )
    if len(files) != len(set(raw_file_ids)):
        raise ValidationError("One or more additional files are unavailable.")
    snapshot = {
        "id": str(plan.pk),
        "slot": plan.slot,
        "name": plan.name,
        "price_minor": plan.price_minor,
        "currency": plan.currency,
        "description": plan.description,
    }
    if not plan.price_minor or not plan.currency:
        raise ValidationError("This revision plan is not ready for checkout.")
    order = RevisionPlanOrder.objects.create(
        client=project.client,
        project=project,
        revision_plan=plan,
        plan_snapshot=snapshot,
        policy_snapshot=current_policy_snapshot(),
        song_reference=song,
        changes=changes,
        amount_minor=plan.price_minor,
        currency=plan.currency,
        request_key=request_key,
    )
    RevisionPlanAttachment.objects.bulk_create(
        [RevisionPlanAttachment(order=order, file=file) for file in files]
    )
    audit(user, "revision_plan_order.created", order.pk, {"project": str(project.pk), "plan": str(plan.pk)})
    return order


@transaction.atomic
def start_revision_checkout(user, order_id, policy_version):
    order = RevisionPlanOrder.objects.select_for_update().filter(pk=order_id, client__user=user).first()
    if not order or order.status != "payment_pending":
        raise ValidationError("This revision order is not awaiting payment.")
    validate_policy_version(order.policy_snapshot, policy_version)
    if not razorpay_test_enabled():
        raise ValidationError("Revision checkout is not configured.")
    existing = order.payments.filter(status="pending").first()
    if existing:
        return existing
    gateway_order = _razorpay_request(
        "POST",
        "orders",
        json={
            "amount": order.amount_minor,
            "currency": order.currency,
            "receipt": f"brio_rev_{order.pk.hex[:20]}",
            "notes": {"brio_revision_order_id": str(order.pk)},
        },
    )
    reference = gateway_order.get("id")
    if (
        not isinstance(reference, str)
        or not reference.startswith("order_")
        or gateway_order.get("amount") != order.amount_minor
        or gateway_order.get("currency") != order.currency
        or gateway_order.get("status") != "created"
    ):
        raise ValidationError("The payment provider returned an invalid order.")
    order.policy_accepted_at = timezone.now()
    order.save(update_fields=["policy_accepted_at", "updated_at"])
    payment = RevisionPlanPayment.objects.create(
        order=order,
        provider="razorpay_test",
        provider_reference=reference,
        amount_minor=order.amount_minor,
        currency=order.currency,
    )
    audit(user, "revision_plan_payment.started", payment.pk, {"order": str(order.pk)})
    return payment


def revision_checkout_data(payment):
    if not razorpay_test_enabled() or payment.status != "pending" or payment.order.status != "payment_pending":
        raise ValidationError("This payment is not awaiting checkout.")
    return {
        "key": settings.RAZORPAY_KEY_ID,
        "amount": payment.amount_minor,
        "currency": payment.currency,
        "order_id": payment.provider_reference,
        "payment_id": str(payment.pk),
    }


@transaction.atomic
def confirm_revision_payment(user, payment_id, payload):
    if not razorpay_test_enabled() or not isinstance(payload, dict) or set(payload) != {
        "razorpay_payment_id", "razorpay_order_id", "razorpay_signature"
    }:
        raise ValidationError("Invalid Razorpay payment response.")
    payment = RevisionPlanPayment.objects.select_for_update().select_related(
        "order__project__client__user"
    ).filter(pk=payment_id, order__client__user=user, provider="razorpay_test").first()
    if not payment:
        raise ValidationError("Unknown Razorpay payment.")
    gateway_id = payload.get("razorpay_payment_id")
    supplied_order = payload.get("razorpay_order_id")
    signature = payload.get("razorpay_signature")
    if any(not isinstance(value, str) or not 1 <= len(value) <= 200 for value in [gateway_id, supplied_order, signature]):
        raise ValidationError("Invalid Razorpay payment response.")
    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        f"{payment.provider_reference}|{gateway_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    if supplied_order != payment.provider_reference or not hmac.compare_digest(expected, signature):
        raise ValidationError("Razorpay payment signature was rejected.")
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    previous = RevisionPlanPaymentEvent.objects.filter(event_id=gateway_id).first()
    if previous:
        if previous.payment_id != payment.pk or previous.payload_digest != digest:
            raise ValidationError("Conflicting Razorpay payment response.")
        return previous
    gateway = _razorpay_request("GET", f"payments/{gateway_id}")
    if (
        gateway.get("id") != gateway_id
        or gateway.get("order_id") != payment.provider_reference
        or gateway.get("amount") != payment.amount_minor
        or gateway.get("currency") != payment.currency
        or gateway.get("status") != "captured"
        or gateway.get("captured") is not True
    ):
        raise ValidationError("Razorpay payment is not captured or does not match this order.")
    order = RevisionPlanOrder.objects.select_for_update().get(pk=payment.order_id)
    if order.status != "payment_pending" or payment.status != "pending":
        raise ValidationError("This payment session is no longer active.")
    project_for(user, order.project_id)
    Order.objects.select_for_update().get(project_id=order.project_id)
    project = Project.objects.select_for_update().get(pk=order.project_id)
    assignment = project.assignments.filter(ended_at__isnull=True).select_related("editor__user").first()
    if not assignment:
        raise ValidationError("The original project's editor is no longer assigned. Contact support.")
    latest = project.versions.order_by("-number").first()
    if not latest or project.status != "awaiting_review":
        raise ValidationError("The selected project is no longer awaiting review.")
    revision = RevisionRequest.objects.create(
        project=project,
        version=latest,
        requested_by=user,
        instructions=order.changes,
        revision_plan_snapshot=order.plan_snapshot,
        song_reference=order.song_reference,
    )
    project.status = "revision_requested"
    project.save(update_fields=["status", "updated_at"])
    order.attachments.update(revision_request=revision)
    now = timezone.now()
    payment.status = "confirmed"
    payment.confirmed_at = now
    payment.save(update_fields=["status", "confirmed_at", "updated_at"])
    order.status = "confirmed"
    order.revision_request = revision
    order.save(update_fields=["status", "revision_request", "updated_at"])
    notify(user, project, f"revision-plan:{order.pk}:client", "Revision plan payment confirmed and sent to your assigned editor.")
    notify(
        assignment.editor.user,
        project,
        f"revision-plan:{order.pk}:editor",
        f"A paid revision was requested on version {latest.number}.",
    )
    notify_admins(project, f"revision-plan:{order.pk}", "A paid revision plan was sent to the original assigned editor.")
    audit(None, "revision_plan_payment.confirmed", payment.pk, {
        "project": str(project.pk), "revision": str(revision.pk), "editor": str(assignment.editor_id),
        "availability_bypassed": True,
    })
    return RevisionPlanPaymentEvent.objects.create(
        payment=payment,
        provider="razorpay_test",
        event_id=gateway_id,
        payload_digest=digest,
        outcome="confirmed",
    )
