"""Authoritative quotes and order agreement snapshots. No prices come from the browser."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .commerce_forms import MAX_PRICE, PlanForm, PolicyForm, ServiceForm
from .models import CommercePolicy, CustomService, Order, OrderQuote, Plan
from .views import audit


def check_policy(policy):
    if not policy or not policy.quotes_enabled:
        raise ValidationError("Pricing is being prepared. You can save your brief and upload files now.")
    values = {field: getattr(policy, field) for field in PolicyForm.Meta.fields}
    if not PolicyForm(values, instance=policy).is_valid():
        raise ValidationError("Commercial terms are incomplete. Please contact the team.")


def ensure_editable(order):
    if (
        order.project.status != "payment_pending"
        or order.payment_status == "confirmed"
        or order.payments.exists()
    ):
        raise ValidationError("This order is locked for payment. Its agreed price cannot be changed.")


def validate_catalog(item, form_class, currency):
    values = {field: getattr(item, field) for field in form_class.Meta.fields}
    if isinstance(item, Plan):
        values["features"] = "\n".join(item.features)
    if not item.active or item.currency != currency or not form_class(values, instance=item).is_valid():
        raise ValidationError("The selected item is unavailable or incomplete. Please choose again.")


@transaction.atomic
def create_quote(user, project_id, kind, plan_id=None, service_ids=()):
    order = Order.objects.select_for_update().get(project_id=project_id, project__client__user=user)
    ensure_editable(order)
    policy = CommercePolicy.objects.select_for_update().filter(pk=1).first()
    check_policy(policy)
    terms = {
        field: getattr(policy, field) for field in ["terms", "delivery_terms", "refund_terms", "tax_terms"]
    }
    items = []
    if kind == "plan":
        plan = Plan.objects.select_for_update().filter(pk=plan_id).first()
        if not plan or service_ids:
            raise ValidationError("Select a valid plan without custom add-ons.")
        validate_catalog(plan, PlanForm, policy.currency)
        items.append({"id": str(plan.id), "name": plan.name, "amount_minor": plan.price_minor})
        details = {
            field: getattr(plan, field)
            for field in [
                "features",
                "revision_limit",
                "delivery_hours",
                "duration_limit_seconds",
                "priority",
            ]
        }
    elif kind == "custom":
        if plan_id or policy.custom_base_minor is None:
            raise ValidationError("Custom pricing is not available yet.")
        ids = set(str(value) for value in service_ids)
        services = list(CustomService.objects.select_for_update().filter(pk__in=ids).order_by("name"))
        if len(services) != len(ids):
            raise ValidationError("A selected service is no longer available.")
        items.append({"id": "base", "name": "Custom editing base", "amount_minor": policy.custom_base_minor})
        for service in services:
            validate_catalog(service, ServiceForm, policy.currency)
            items.append({"id": str(service.id), "name": service.name, "amount_minor": service.price_minor})
        details = {
            field: getattr(policy, f"custom_{field}")
            for field in ["revision_limit", "delivery_hours", "duration_limit_seconds", "priority"]
        }
        details["features"] = [service.name for service in services]
    else:
        raise ValidationError("Choose a plan or custom editing.")
    total = sum(item["amount_minor"] for item in items)
    if not 0 < total <= MAX_PRICE:
        raise ValidationError("The quote total is outside the supported range. Contact the team.")
    snapshot = {
        "version": 1,
        "kind": kind,
        "plan_id": str(plan_id) if kind == "plan" else None,
        "items": items,
        "terms": terms,
        **details,
        "currency": policy.currency,
        "total_minor": total,
        "deadline_rule": "pending_owner_decision",
        "earning_rule_version": None,
        "review_rule": policy.review_rule,
        "scope": "Selected plan/services only; unpriced extras require team review.",
    }
    quote = OrderQuote.objects.create(
        order=order, snapshot=snapshot, total_minor=total, currency=policy.currency
    )
    audit(user, "quote.created", quote.id, {"order": str(order.id)})
    return quote


@transaction.atomic
def accept_quote(user, project_id, quote_id):
    order = Order.objects.select_for_update().get(project_id=project_id, project__client__user=user)
    quote = OrderQuote.objects.get(pk=quote_id, order=order)
    if str(order.terms_snapshot.get("quote_id")) == str(quote.id):
        return order
    ensure_editable(order)
    if order.quotes.first().pk != quote.pk:
        raise ValidationError("A newer quote exists. Please review the latest quote.")
    # A displayed quote is honored as quoted; catalog edits never rewrite it.
    quote.accepted_at = timezone.now()
    quote.save(update_fields=["accepted_at", "updated_at"])
    order.kind = quote.snapshot["kind"]
    order.plan_id = quote.snapshot["plan_id"]
    order.total_minor = quote.total_minor
    order.currency = quote.currency
    order.terms_snapshot = {
        **quote.snapshot,
        "quote_id": str(quote.id),
        "accepted_at": quote.accepted_at.isoformat(),
    }
    order.save(update_fields=["kind", "plan", "total_minor", "currency", "terms_snapshot", "updated_at"])
    audit(user, "quote.accepted", quote.id, {"order": str(order.id)})
    return order
