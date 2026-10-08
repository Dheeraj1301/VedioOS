from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .commerce import accept_quote, check_policy, create_quote, custom_estimate_result
from .commerce_forms import (
    CustomEstimateForm,
    PackageForm,
    PlanForm,
    PolicyForm,
    QuotationFeatureForm,
    QuoteSelectionForm,
    ServiceForm,
)
from .models import (
    CommercePolicy,
    CustomService,
    InfluencerPackage,
    OrderQuote,
    Payment,
    Plan,
    QuotationFeature,
)
from .payments import apply_sandbox_event, sandbox_enabled, start_checkout
from .permissions import project_for, role_required, visible_files
from .templatetags.money import money
from .views import audit


@role_required("admin")
def pricing(request):
    return render(
        request,
        "commerce/pricing.html",
        {
            "title": "Plans / Pricing",
            "slots": [
                (slot, Plan.objects.filter(slot=slot).first() or Plan(slot=slot)) for slot in range(1, 4)
            ],
            "services": CustomService.objects.order_by("name"),
            "quotation_features": QuotationFeature.objects.order_by("code"),
            "packages": InfluencerPackage.objects.order_by("name"),
            "policy": CommercePolicy.objects.filter(pk=1).first() or CommercePolicy(),
        },
    )


@role_required("admin")
def catalog_edit(request, kind, slot=None, item_id=None, feature_code=None):
    if kind == "plan":
        if slot not in [1, 2, 3]:
            raise PermissionDenied
        instance = Plan.objects.filter(slot=slot).first() or Plan(slot=slot)
        form_class, title = PlanForm, f"Plan {slot}"
    elif kind == "service":
        instance = get_object_or_404(CustomService, pk=item_id) if item_id else CustomService()
        form_class, title = ServiceForm, "Custom service"
    elif kind == "package":
        instance = get_object_or_404(InfluencerPackage, pk=item_id) if item_id else InfluencerPackage()
        form_class, title = PackageForm, "Monthly creator package draft"
    elif kind == "quotation_feature":
        instance = get_object_or_404(QuotationFeature, code=feature_code)
        form_class, title = QuotationFeatureForm, instance.get_code_display()
    else:
        instance = CommercePolicy.objects.filter(pk=1).first() or CommercePolicy(pk=1)
        form_class, title = PolicyForm, "Commercial terms & custom pricing"
    form = form_class(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                item = form.save()
                if kind == "package" and item.active:
                    item.active = False
                    item.save(update_fields=["active", "updated_at"])
                audit(request.user, f"catalog.{kind}_saved", item.pk)
            messages.success(request, "Saved. Existing accepted order terms are unchanged.")
            return redirect("pricing")
        except IntegrityError:
            form.add_error(None, "This item was changed elsewhere or already exists. Reload and try again.")
    return render(request, "commerce/edit.html", {"title": title, "form": form})


@role_required("client")
def quote_page(request, project_id):
    project = project_for(request.user, project_id)
    policy = CommercePolicy.objects.filter(pk=1).first()
    unavailable = ""
    try:
        check_policy(policy)
    except ValidationError as exc:
        unavailable = " ".join(exc.messages)
    initial = None
    if request.method != "POST":
        initial = {
            "kind": project.order.kind,
            "plan": project.order.plan_id,
            "pricing_period": project.order.pricing_period,
        }
    form = QuoteSelectionForm(
        request.POST or None,
        currency=policy.currency if policy else "",
        initial=initial,
    )
    if request.method == "POST":
        if set(request.POST) - {
            "csrfmiddlewaretoken",
            "kind",
            "plan",
            "pricing_period",
            "services",
            "scope_confirmed",
        }:
            return render(
                request,
                "error.html",
                {"message": "Only catalog selections are accepted. Prices are calculated by the server."},
                status=400,
            )
        if form.is_valid():
            try:
                quote = create_quote(
                    request.user,
                    project.id,
                    form.cleaned_data["kind"],
                    plan_id=(
                        form.cleaned_data["plan"].pk if form.cleaned_data["plan"] else None
                    ),
                    service_ids=[item.pk for item in form.cleaned_data["services"]],
                    pricing_period=form.cleaned_data["pricing_period"],
                )
                return redirect("quote_review", project_id=project.id, quote_id=quote.id)
            except ValidationError as exc:
                form.add_error(None, exc)
    return render(
        request,
        "commerce/select.html",
        {
            "title": "Choose your edit",
            "project": project,
            "form": form,
            "unavailable": unavailable,
            "policy": policy,
            "plans": form.fields["plan"].queryset,
            "services": form.fields["services"].queryset,
            "locked": project.order.payments.exists() or project.status != "payment_pending",
        },
    )


@require_POST
@role_required("client")
def estimate_custom(request):
    allowed = {
        "colour_grading",
        "quality_enhancement",
        "reel_duration",
        "wants_wording",
        "wording_direction",
        "song_choice",
        "overlays",
        "beat_sync",
    }
    try:
        import json

        data = json.loads(request.body)
        if not isinstance(data, dict) or set(data) - allowed:
            raise ValueError
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid customization selection."}, status=400)
    form = CustomEstimateForm(data)
    if not form.is_valid():
        return JsonResponse(
            {"error": "Check the customization selections.", "fields": form.errors.get_json_data()},
            status=400,
        )
    try:
        result = custom_estimate_result(form.cleaned_data)
    except ValidationError as exc:
        return JsonResponse({"error": " ".join(exc.messages)}, status=409)
    policy = result["policy"]
    items = result["items"]
    total = result["total_minor"]
    return JsonResponse(
        {
            "currency": policy.currency,
            "total_minor": total,
            "display_total": money(total, policy.currency),
            "items": [
                {**item, "display_amount": money(item["amount_minor"], policy.currency)}
                for item in items
            ],
            "breakdown": [
                {**item, "display_amount": money(item["amount_minor"], policy.currency)}
                for item in result["breakdown"]
            ],
            "model": result["quotation"].get("model"),
        }
    )


@role_required("client")
def quote_review(request, project_id, quote_id):
    project = project_for(request.user, project_id)
    quote = get_object_or_404(OrderQuote, pk=quote_id, order__project=project)
    if request.method == "POST":
        if set(request.POST) != {"csrfmiddlewaretoken", "agree"} or request.POST.get("agree") != "yes":
            messages.error(request, "Confirm you accept the displayed quote and terms.")
        else:
            try:
                accept_quote(request.user, project.id, quote.id)
                messages.success(request, "Quote accepted. Your price and terms have been saved.")
                return redirect("order_summary", project_id=project.id)
            except ValidationError as exc:
                messages.error(request, " ".join(exc.messages))
    return render(
        request,
        "commerce/review.html",
        {
            "title": "Review your quote",
            "project": project,
            "quote": quote,
            "snapshot": quote.snapshot,
        },
    )


@role_required("client")
def custom_checkout(request, project_id):
    project = project_for(request.user, project_id)
    order = project.order
    if order.kind != "custom":
        return redirect("client_project", project_id=project.id)

    if order.payment_status == "confirmed":
        snapshot = order.terms_snapshot
        quote = order.quotes.filter(pk=snapshot.get("quote_id")).first() if snapshot else None
    else:
        quote = order.quotes.first()
        snapshot = quote.snapshot if quote else None

    if not snapshot or not quote:
        messages.error(
            request,
            "Complete the customization form and save it to generate your quotation before payment.",
        )
        return redirect("edit_project", project_id=project.id)

    total = snapshot.get("total_minor")
    currency = snapshot.get("currency")
    valid_total = (
        type(total) is int
        and total > 0
        and total == quote.total_minor
        and isinstance(currency, str)
        and currency == quote.currency
    )
    if request.method == "POST":
        if set(request.POST) - {"csrfmiddlewaretoken", "agree"}:
            raise PermissionDenied
        if order.payment_status == "confirmed":
            messages.info(request, "Payment has already been completed for this project.")
        elif not valid_total:
            messages.error(request, "This quotation has an invalid total and cannot be paid.")
        elif request.POST.get("agree") != "yes":
            messages.error(request, "Accept the displayed quotation and terms before payment.")
        else:
            try:
                with transaction.atomic():
                    accept_quote(request.user, project.id, quote.id)
                    start_checkout(request.user, project.id)
                messages.success(
                    request,
                    "Payment was started using the saved quotation amount and currency.",
                )
                return redirect("order_summary", project_id=project.id)
            except ValidationError as exc:
                messages.error(request, " ".join(exc.messages))

    features = snapshot.get("features", [])
    if not isinstance(features, list):
        features = []
    breakdown = snapshot.get("estimate_breakdown", [])
    if not isinstance(breakdown, list):
        breakdown = []
    return render(
        request,
        "commerce/custom_checkout.html",
        {
            "title": "Custom quotation and payment",
            "project": project,
            "order": order,
            "quote": quote,
            "snapshot": snapshot,
            "features": features,
            "breakdown": breakdown,
            "files": visible_files(request.user, project),
            "valid_total": valid_total,
            "sandbox": sandbox_enabled(),
        },
    )


@role_required("client", "admin")
def order_summary(request, project_id):
    project = project_for(request.user, project_id)
    return render(
        request,
        "commerce/order.html",
        {
            "title": "Order summary",
            "project": project,
            "order": project.order,
            "snapshot": project.order.terms_snapshot,
            "sandbox": sandbox_enabled(),
            "payments": project.order.payments.order_by("-created_at"),
        },
    )


@require_POST
@role_required("client")
def checkout(request, project_id):
    project = project_for(request.user, project_id)
    if set(request.POST) - {"csrfmiddlewaretoken"}:
        raise PermissionDenied
    try:
        start_checkout(request.user, project.id)
        messages.success(
            request,
            "Development payment created. No money was charged. Awaiting the signed sandbox gateway event.",
        )
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    return redirect("order_summary", project_id=project.id)


@csrf_exempt
@require_POST
def sandbox_webhook(request):
    if not sandbox_enabled():
        return JsonResponse({"error": "Gateway disabled."}, status=503)
    try:
        event = apply_sandbox_event(request.body, request.headers.get("X-Sandbox-Signature", ""))
    except (ValidationError, IntegrityError):
        return JsonResponse({"error": "Payment event rejected."}, status=400)
    return JsonResponse({"received": str(event.id)})


@role_required("client", "admin")
def payment_receipt(request, payment_id):
    payment = get_object_or_404(Payment, pk=payment_id, status="confirmed")
    project = project_for(request.user, payment.order.project_id)
    return render(
        request,
        "commerce/receipt.html",
        {
            "title": "Payment receipt",
            "payment": payment,
            "project": project,
            "snapshot": payment.order.terms_snapshot,
        },
    )
