"""Authoritative quotes and order agreement snapshots. No prices come from the browser."""

from copy import deepcopy
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from operations.earnings import quote_rule
from operations.models import EarningPolicy

from .commerce_forms import MAX_PRICE, PlanForm, PolicyForm, ServiceForm
from .models import CommercePolicy, CustomService, Order, OrderQuote, Plan, Project, QuotationFeature
from .views import audit

CUSTOM_CODE_LABELS = dict(CustomService.Code.choices)


def custom_service_codes(subject):
    """Return stable catalog codes implied by a saved project or validated estimate data."""

    get = subject.get if isinstance(subject, dict) else lambda key, default=None: getattr(
        subject, key, default
    )
    codes = []
    if get("colour_grading", False):
        codes.append(CustomService.Code.COLOUR_GRADING)
    if get("quality_enhancement", False):
        codes.append(CustomService.Code.QUALITY_ENHANCEMENT)
    duration = get("reel_duration", "")
    if duration:
        codes.append(f"duration_{duration}")
    if get("wants_wording", False):
        codes.append(CustomService.Code.WORDING)
    return codes


def _subject_value(subject, key, default=None):
    return subject.get(key, default) if isinstance(subject, dict) else getattr(subject, key, default)


def _legacy_custom_estimate(subject, policy, *, lock=False):
    codes = custom_service_codes(subject)
    service_query = CustomService.objects.select_for_update() if lock else CustomService.objects
    services = list(service_query.filter(code__in=codes).order_by("name"))
    found = {service.code for service in services}
    missing = [CUSTOM_CODE_LABELS.get(code, code) for code in codes if code not in found]
    if missing:
        raise ValidationError(
            "Pricing is not configured for: " + ", ".join(missing) + ". Contact the team."
        )
    items = [{"id": "base", "name": "Custom editing base", "amount_minor": policy.custom_base_minor}]
    for service in services:
        validate_catalog(service, ServiceForm, policy.currency)
        items.append({"id": str(service.id), "name": service.name, "amount_minor": service.price_minor})
    total = sum(item["amount_minor"] for item in items)
    return {
        "policy": policy,
        "services": services,
        "items": items,
        "breakdown": items,
        "total_minor": total,
        "quotation": {"version": 1, "model": "catalog_v1"},
    }


def _weighted_feature_selections(subject):
    duration = _subject_value(subject, "reel_duration", "")
    wording = _subject_value(subject, "wording_direction", "")
    song = _subject_value(subject, "song_choice", "")
    duration_labels = dict(Project.ReelDuration.choices)
    wording_labels = dict(Project.WordingDirection.choices)
    song_labels = dict(Project._meta.get_field("song_choice").choices)
    selections = []
    if _subject_value(subject, "colour_grading", False):
        selections.append((QuotationFeature.Code.COLOUR_GRADING, "Colour grading"))
    if _subject_value(subject, "quality_enhancement", False):
        selections.append((QuotationFeature.Code.QUALITY_ENHANCEMENT, "Quality enhancement"))
    if duration:
        selections.append(
            (QuotationFeature.Code.DURATION, f"Duration: {duration_labels.get(duration, duration)}")
        )
    if _subject_value(subject, "wants_wording", False):
        selections.append(
            (QuotationFeature.Code.FONT_OPTION, f"Font option: {wording_labels.get(wording, wording)}")
        )
    if song:
        selections.append((QuotationFeature.Code.SONG_OPTION, f"Song option: {song_labels.get(song, song)}"))
    if _subject_value(subject, "overlays", False):
        selections.append((QuotationFeature.Code.OVERLAYS, "Overlays"))
    if _subject_value(subject, "beat_sync", False):
        selections.append((QuotationFeature.Code.BEAT_SYNC, "Beat sync"))
    return selections


def _weighted_custom_estimate(subject, policy, *, lock=False):
    required = {value for value, _ in QuotationFeature.Code.choices}
    feature_query = QuotationFeature.objects.select_for_update() if lock else QuotationFeature.objects
    configured = {feature.code: feature for feature in feature_query.filter(code__in=required)}
    missing = sorted(required - set(configured))
    if missing:
        raise ValidationError("Weighted quotation feature scores are incomplete. Contact the team.")
    if any(
        value is None
        for value in [
            policy.custom_base_minor,
            policy.quotation_point_minor,
            policy.quotation_min_minor,
            policy.quotation_max_minor,
        ]
    ):
        raise ValidationError("Weighted quotation price mapping is incomplete. Contact the team.")
    weights = {
        "time": policy.quotation_time_weight,
        "importance": policy.quotation_importance_weight,
        "complexity": policy.quotation_complexity_weight,
    }
    if sum(weights.values()) != 100:
        raise ValidationError("Weighted quotation percentages must total 100%. Contact the team.")
    selections = _weighted_feature_selections(subject)
    breakdown = [
        {"id": "base", "name": "Custom editing base", "amount_minor": policy.custom_base_minor}
    ]
    feature_snapshot = []
    total_score = Decimal("0")
    for code, label in selections:
        feature = configured[code]
        weighted_score = (
            Decimal(feature.time_score * weights["time"])
            + Decimal(feature.importance_score * weights["importance"])
            + Decimal(feature.complexity_score * weights["complexity"])
        ) / Decimal(100)
        adjusted_score = weighted_score * feature.multiplier
        contribution = int(
            (adjusted_score * Decimal(policy.quotation_point_minor)).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )
        total_score += adjusted_score
        breakdown.append({"id": code, "name": label, "amount_minor": contribution})
        feature_snapshot.append(
            {
                "code": code,
                "name": label,
                "time": feature.time_score,
                "importance": feature.importance_score,
                "complexity": feature.complexity_score,
                "multiplier": str(feature.multiplier),
                "weighted_score": str(weighted_score.normalize()),
                "adjusted_score": str(adjusted_score.normalize()),
                "amount_minor": contribution,
            }
        )
    raw_total = sum(item["amount_minor"] for item in breakdown)
    total = max(policy.quotation_min_minor, min(raw_total, policy.quotation_max_minor))
    items = [{"id": "weighted-estimate", "name": "Weighted custom estimate", "amount_minor": total}]
    quotation = {
        "version": 1,
        "model": "weighted_heuristic_v1",
        "prediction_source": "heuristic",
        "weights": weights,
        "price_per_point_minor": policy.quotation_point_minor,
        "base_minor": policy.custom_base_minor,
        "minimum_minor": policy.quotation_min_minor,
        "maximum_minor": policy.quotation_max_minor,
        "raw_total_minor": raw_total,
        "total_complexity_score": str(total_score.normalize()),
        "features": feature_snapshot,
        "inputs": {
            "colour_grading": bool(_subject_value(subject, "colour_grading", False)),
            "quality_enhancement": bool(_subject_value(subject, "quality_enhancement", False)),
            "reel_duration": _subject_value(subject, "reel_duration", ""),
            "wants_wording": bool(_subject_value(subject, "wants_wording", False)),
            "wording_direction": _subject_value(subject, "wording_direction", ""),
            "song_choice": _subject_value(subject, "song_choice", ""),
            "overlays": bool(_subject_value(subject, "overlays", False)),
            "beat_sync": bool(_subject_value(subject, "beat_sync", False)),
        },
    }
    return {
        "policy": policy,
        "services": [],
        "items": items,
        "breakdown": breakdown,
        "total_minor": total,
        "quotation": quotation,
    }


def custom_estimate_result(subject, *, lock=False):
    policy_query = CommercePolicy.objects.select_for_update() if lock else CommercePolicy.objects
    policy = policy_query.filter(pk=1).first()
    check_policy(policy)
    if policy.custom_base_minor is None:
        raise ValidationError("Custom pricing is not available yet.")
    result = (
        _weighted_custom_estimate(subject, policy, lock=lock)
        if policy.quotation_engine_enabled
        else _legacy_custom_estimate(subject, policy, lock=lock)
    )
    total = result["total_minor"]
    if not 0 < total <= MAX_PRICE:
        raise ValidationError("The estimate total is outside the supported range. Contact the team.")
    return result


def custom_estimate(subject, *, lock=False):
    result = custom_estimate_result(subject, lock=lock)
    return result["policy"], result["services"], result["items"], result["total_minor"]


def saved_custom_estimate_snapshot(subject, *, lock=False):
    result = custom_estimate_result(subject, lock=lock)
    return {
        "version": 1,
        "pricing_context": result["policy"].pricing_context,
        "currency": result["policy"].currency,
        "total_minor": result["total_minor"],
        "items": deepcopy(result["items"]),
        "breakdown": deepcopy(result["breakdown"]),
        "quotation": deepcopy(result["quotation"]),
    }


def check_policy(policy):
    if not policy or not policy.quotes_enabled:
        raise ValidationError("Pricing is being prepared. You can save your brief and upload files now.")
    if policy.pricing_context == CommercePolicy.PricingContext.TEST and not (
        settings.DEBUG and settings.PAYMENT_MODE in {"sandbox", "razorpay_test"}
    ):
        raise ValidationError("Test-only pricing is unavailable outside a test payment environment.")
    if policy.pricing_context == CommercePolicy.PricingContext.UNCONFIGURED:
        raise ValidationError("Pricing context is not configured. Please contact the team.")
    values = {field: getattr(policy, field) for field in PolicyForm.Meta.fields}
    if not PolicyForm(values, instance=policy, values_are_minor=True).is_valid():
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
    if (
        not item.active
        or item.currency != currency
        or not form_class(values, instance=item, values_are_minor=True).is_valid()
    ):
        raise ValidationError("The selected item is unavailable or incomplete. Please choose again.")


def normalize_pricing_period(pricing_period):
    valid_periods = {value for value, _ in Plan.PricingPeriod.choices}
    if pricing_period not in valid_periods:
        raise ValidationError("Choose a valid pricing period.")
    return pricing_period


def _validated_saved_weighted_estimate(project):
    snapshot = project.quotation_snapshot
    if not isinstance(snapshot, dict):
        return None
    quotation = snapshot.get("quotation")
    items = snapshot.get("items")
    total = snapshot.get("total_minor")
    currency = snapshot.get("currency")
    pricing_context = snapshot.get("pricing_context")
    if (
        not isinstance(quotation, dict)
        or quotation.get("model") != "weighted_heuristic_v1"
        or not isinstance(items, list)
        or not items
        or type(total) is not int
        or total <= 0
        or not isinstance(currency, str)
        or len(currency) != 3
        or pricing_context not in {
            CommercePolicy.PricingContext.TEST,
            CommercePolicy.PricingContext.PRODUCTION,
        }
    ):
        return None
    if any(
        not isinstance(item, dict)
        or type(item.get("amount_minor")) is not int
        or item["amount_minor"] <= 0
        for item in items
    ):
        return None
    if sum(item["amount_minor"] for item in items) != total:
        return None
    return deepcopy(snapshot)


@transaction.atomic
def create_quote(
    user,
    project_id,
    kind,
    plan_id=None,
    service_ids=(),
    pricing_period=Plan.PricingPeriod.PER_REEL,
):
    order = Order.objects.select_for_update().get(project_id=project_id, project__client__user=user)
    ensure_editable(order)
    policy = CommercePolicy.objects.select_for_update().filter(pk=1).first()
    check_policy(policy)
    terms = {
        field: getattr(policy, field) for field in ["terms", "delivery_terms", "refund_terms", "tax_terms"]
    }
    items = []
    quote_currency = policy.currency
    quotation = None
    pricing_context = policy.pricing_context
    if kind == "plan":
        pricing_period = normalize_pricing_period(pricing_period)
        plan = Plan.objects.select_for_update().filter(pk=plan_id).first()
        if not plan or service_ids:
            raise ValidationError("Select a valid plan without custom add-ons.")
        validate_catalog(plan, PlanForm, policy.currency)
        plan_price = plan.price_for_period(pricing_period)
        if not plan_price:
            raise ValidationError("That plan is not configured for the selected pricing period.")
        items.append({"id": str(plan.id), "name": plan.name, "amount_minor": plan_price})
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
        pricing_period = Plan.PricingPeriod.PER_REEL
        if plan_id:
            raise ValidationError("Custom pricing is not available yet.")
        ids = set(str(value) for value in service_ids)
        services = list(CustomService.objects.select_for_update().filter(pk__in=ids).order_by("name"))
        if len(services) != len(ids):
            raise ValidationError("A selected service is no longer available.")
        saved_estimate = _validated_saved_weighted_estimate(order.project)
        if saved_estimate:
            required_services = []
            items = saved_estimate["items"]
            quote_currency = saved_estimate["currency"]
            quotation = saved_estimate["quotation"]
            estimate_breakdown = saved_estimate.get("breakdown", [])
            pricing_context = saved_estimate["pricing_context"]
        else:
            estimate_result = custom_estimate_result(order.project, lock=True)
            required_services = estimate_result["services"]
            items = estimate_result["items"]
            quotation = estimate_result["quotation"]
            estimate_breakdown = estimate_result["breakdown"]
        required_ids = {service.id for service in required_services}
        for service in services:
            if service.id in required_ids:
                continue
            validate_catalog(service, ServiceForm, quote_currency)
            items.append({"id": str(service.id), "name": service.name, "amount_minor": service.price_minor})
        details = {
            field: getattr(policy, f"custom_{field}")
            for field in ["revision_limit", "delivery_hours", "duration_limit_seconds", "priority"]
        }
        details["features"] = [
            feature["name"] for feature in (quotation or {}).get("features", [])
        ] + [item["name"] for item in items if item["id"] not in {"base", "weighted-estimate"}]
        details["quotation"] = quotation
        details["estimate_breakdown"] = estimate_breakdown
    else:
        raise ValidationError("Choose a plan or custom editing.")
    total = sum(item["amount_minor"] for item in items)
    if not 0 < total <= MAX_PRICE:
        raise ValidationError("The quote total is outside the supported range. Contact the team.")
    snapshot = {
        "version": 2,
        "pricing_context": pricing_context,
        "kind": kind,
        "plan_id": str(plan_id) if kind == "plan" else None,
        "pricing_period": pricing_period,
        "items": items,
        "terms": terms,
        **details,
        "currency": quote_currency,
        "total_minor": total,
        "deadline_rule": "pending_owner_decision",
        "earning_rule_version": None,
        "earning_rule": quote_rule(
            kind, plan if kind == "plan" else None, EarningPolicy.objects.filter(pk=1).first()
        ),
        "review_rule": policy.review_rule,
        "scope": "Selected plan/services only; unpriced extras require team review.",
    }
    quote = OrderQuote.objects.create(
        order=order, snapshot=snapshot, total_minor=total, currency=quote_currency
    )
    audit(user, "quote.created", quote.id, {"order": str(order.id)})
    return quote


@transaction.atomic
def accept_quote(user, project_id, quote_id):
    order = Order.objects.select_for_update().get(project_id=project_id, project__client__user=user)
    quote = OrderQuote.objects.get(pk=quote_id, order=order)
    if quote.snapshot.get("pricing_context") == CommercePolicy.PricingContext.TEST and not (
        settings.DEBUG and settings.PAYMENT_MODE in {"sandbox", "razorpay_test"}
    ):
        raise ValidationError("This test-only quotation cannot be accepted outside test mode.")
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
    order.pricing_period = quote.snapshot.get(
        "pricing_period", Plan.PricingPeriod.PER_REEL
    )
    order.total_minor = quote.total_minor
    order.currency = quote.currency
    order.terms_snapshot = {
        **quote.snapshot,
        "quote_id": str(quote.id),
        "accepted_at": quote.accepted_at.isoformat(),
    }
    order.save(
        update_fields=[
            "kind",
            "plan",
            "pricing_period",
            "total_minor",
            "currency",
            "terms_snapshot",
            "updated_at",
        ]
    )
    audit(user, "quote.accepted", quote.id, {"order": str(order.id)})
    return order
