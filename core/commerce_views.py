import json

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .commerce import (
    accept_quote,
    check_policy,
    create_quote,
    custom_estimate_result,
)
from .commerce_forms import (
    CustomEstimateForm,
    PackageForm,
    PlanForm,
    PolicyForm,
    QuotationFeatureForm,
    QuoteSelectionForm,
    RevisionPlanForm,
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
    RevisionPlan,
    RevisionPlanOrder,
    RevisionPlanPayment,
    UploadPolicy,
)
from .payments import (
    apply_sandbox_event,
    confirm_razorpay_test_payment,
    razorpay_checkout_data,
    razorpay_test_enabled,
    sandbox_enabled,
    start_checkout,
)
from .permissions import project_for, role_required, visible_files
from .policies import payment_policy_snapshot, record_payment_acceptance
from .revision_checkout import (
    confirm_revision_payment,
    create_revision_order,
    eligible_revision_projects,
    revision_checkout_data,
    start_revision_checkout,
)
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
            "revision_slots": [
                (
                    slot,
                    RevisionPlan.objects.filter(slot=slot).first() or RevisionPlan(slot=slot),
                )
                for slot in range(1, 4)
            ],
            "services": CustomService.objects.order_by("name"),
            "quotation_features": QuotationFeature.objects.order_by("code"),
            "packages": InfluencerPackage.objects.order_by("name"),
            "policy": CommercePolicy.objects.filter(pk=1).first() or CommercePolicy(),
        },
    )


@role_required("admin")
def catalog_edit(request, kind, slot=None, item_id=None, feature_code=None):
    previous_policy = None
    if kind == "plan":
        if slot not in [1, 2, 3]:
            raise PermissionDenied
        instance = Plan.objects.filter(slot=slot).first() or Plan(slot=slot)
        form_class, title = PlanForm, f"Plan {slot}"
    elif kind == "revision_plan":
        if slot not in [1, 2, 3]:
            raise PermissionDenied
        instance = RevisionPlan.objects.filter(slot=slot).first() or RevisionPlan(slot=slot)
        form_class, title = RevisionPlanForm, f"Revision plan {slot}"
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
        previous_policy = CommercePolicy.objects.filter(pk=1).first()
        instance = previous_policy or CommercePolicy(pk=1)
        form_class, title = PolicyForm, "Commercial terms & custom pricing"
    form = form_class(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                item = form.save(commit=False)
                if previous_policy and any(
                    field in form.changed_data
                    for field in [
                        "registration_terms",
                        "terms",
                        "delivery_terms",
                        "refund_terms",
                        "no_refund_policy",
                        "tax_terms",
                        "support_statement",
                    ]
                ):
                    item.policy_version = previous_policy.policy_version + 1
                item.save()
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
def revision_plans(request):
    published_plans = list(RevisionPlan.objects.filter(active=True).order_by("slot"))
    return render(
        request,
        "client/revisions.html",
        {
            "title": "Revisions",
            "revision_plans": published_plans,
            "eligible_projects": eligible_revision_projects(request.user),
            "upload_policy": UploadPolicy.objects.filter(pk=1, enabled=True).first(),
        },
    )


@require_POST
@role_required("client")
def revision_order_create(request):
    try:
        order = create_revision_order(request.user, json.loads(request.body))
    except (json.JSONDecodeError, ValidationError) as exc:
        message = exc.messages[0] if isinstance(exc, ValidationError) else "Invalid revision request."
        return JsonResponse({"error": message}, status=400)
    return JsonResponse({"order_id": str(order.pk), "redirect": reverse("revision_order_summary", args=[order.pk])}, status=201)


@role_required("client")
def revision_order_summary(request, order_id):
    order = get_object_or_404(
        RevisionPlanOrder.objects.select_related("project", "revision_plan"),
        pk=order_id,
        client__user=request.user,
    )
    return render(request, "commerce/revision_order.html", {
        "title": "Revision checkout",
        "revision_order": order,
        "attachments": order.attachments.select_related("file"),
        "pending_payment": order.payments.filter(status="pending").first(),
        "razorpay_test": razorpay_test_enabled(),
        "payment_policy": order.policy_snapshot,
    })


@require_POST
@role_required("client")
def revision_order_checkout(request, order_id):
    if request.POST.get("agree") != "yes":
        messages.error(request, "Accept the Terms & Conditions before payment.")
        return redirect("revision_order_summary", order_id=order_id)
    try:
        payment = start_revision_checkout(request.user, order_id, request.POST.get("policy_version"))
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("revision_order_summary", order_id=order_id)
    return redirect("revision_razorpay_checkout", payment_id=payment.pk)


@role_required("client")
def revision_razorpay_checkout(request, payment_id):
    payment = get_object_or_404(
        RevisionPlanPayment.objects.select_related("order__project"),
        pk=payment_id,
        order__client__user=request.user,
        provider="razorpay_test",
    )
    try:
        checkout = revision_checkout_data(payment)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("revision_order_summary", order_id=payment.order_id)
    return render(request, "commerce/revision_razorpay_checkout.html", {
        "title": "Revision payment",
        "payment": payment,
        "revision_order": payment.order,
        "checkout": checkout,
    })


@require_POST
@role_required("client")
def revision_razorpay_confirm(request, payment_id):
    try:
        event = confirm_revision_payment(request.user, payment_id, json.loads(request.body))
    except (json.JSONDecodeError, ValidationError, IntegrityError):
        return JsonResponse({"error": "The revision payment could not be verified."}, status=400)
    return JsonResponse({
        "confirmed": True,
        "event_id": str(event.pk),
        "redirect": reverse("revision_order_summary", args=[event.payment.order_id]),
    })


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
        "revisions_needed",
    }
    try:
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

    if request.method != "POST":
        return redirect("order_summary", project_id=project.id)

    total = snapshot.get("total_minor")
    currency = snapshot.get("currency")
    valid_total = (
        type(total) is int
        and total > 0
        and total == quote.total_minor
        and isinstance(currency, str)
        and currency == quote.currency
    )
    if set(request.POST) - {"csrfmiddlewaretoken", "agree", "policy_version"}:
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
                order.refresh_from_db(fields=["terms_snapshot"])
                record_payment_acceptance(
                    request.user,
                    order,
                    request.POST.get("policy_version"),
                )
                payment = start_checkout(request.user, project.id)
            messages.success(
                request,
                "Payment was started using the saved quotation amount and currency.",
            )
            if payment.provider == "razorpay_test":
                return redirect("razorpay_checkout", payment_id=payment.id)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
    return redirect("order_summary", project_id=project.id)


@role_required("client", "admin")
def order_summary(request, project_id):
    project = project_for(request.user, project_id)
    order = project.order
    quote = None
    snapshot = order.terms_snapshot
    if order.kind == "custom":
        if snapshot:
            quote = order.quotes.filter(pk=snapshot.get("quote_id")).first()
        else:
            quote = order.quotes.first()
            snapshot = quote.snapshot if quote else {}
    custom_features = snapshot.get("features", []) if isinstance(snapshot, dict) else []
    if not isinstance(custom_features, list):
        custom_features = []
    custom_breakdown = (
        snapshot.get("estimate_breakdown", []) if isinstance(snapshot, dict) else []
    )
    if not isinstance(custom_breakdown, list):
        custom_breakdown = []
    valid_custom_total = bool(
        quote
        and type(snapshot.get("total_minor")) is int
        and snapshot["total_minor"] > 0
        and snapshot["total_minor"] == quote.total_minor
        and snapshot.get("currency") == quote.currency
    )
    return render(
        request,
        "commerce/order.html",
        {
            "title": "Order summary",
            "project": project,
            "order": order,
            "snapshot": snapshot,
            "quote": quote,
            "custom_features": custom_features,
            "custom_breakdown": custom_breakdown,
            "valid_custom_total": valid_custom_total,
            "files": visible_files(request.user, project),
            "sandbox": sandbox_enabled(),
            "razorpay_test": razorpay_test_enabled(),
            "payments": project.order.payments.order_by("-created_at"),
            "payment_policy": payment_policy_snapshot(order) if snapshot else None,
        },
    )


@require_POST
@role_required("client")
def checkout(request, project_id):
    project = project_for(request.user, project_id)
    if set(request.POST) - {"csrfmiddlewaretoken", "agree", "policy_version"}:
        raise PermissionDenied
    if request.POST.get("agree") != "yes":
        messages.error(request, "Accept the displayed Terms and Conditions before payment.")
        return redirect("order_summary", project_id=project.id)
    try:
        with transaction.atomic():
            record_payment_acceptance(
                request.user,
                project.order,
                request.POST.get("policy_version"),
            )
            payment = start_checkout(request.user, project.id)
        if payment.provider == "razorpay_test":
            return redirect("razorpay_checkout", payment_id=payment.id)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    return redirect("order_summary", project_id=project.id)


@role_required("client")
def razorpay_checkout(request, payment_id):
    payment = get_object_or_404(
        Payment.objects.select_related("order__project__client__user"),
        pk=payment_id,
        order__project__client__user=request.user,
        provider="razorpay_test",
    )
    try:
        checkout_data = razorpay_checkout_data(payment)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("order_summary", project_id=payment.order.project_id)
    return render(
        request,
        "commerce/razorpay_checkout.html",
        {
            "title": "Secure checkout",
            "payment": payment,
            "project": payment.order.project,
            "checkout": checkout_data,
            "auto_open": payment.order.kind == "plan",
        },
    )


@require_POST
@role_required("client")
def razorpay_confirm(request, payment_id):
    try:
        payload = json.loads(request.body)
        event = confirm_razorpay_test_payment(request.user, payment_id, payload)
    except (json.JSONDecodeError, ValidationError, IntegrityError):
        return JsonResponse({"error": "The payment could not be verified."}, status=400)
    return JsonResponse(
        {
            "confirmed": True,
            "event_id": str(event.id),
            "redirect": reverse("payment_receipt", args=[event.payment_id]),
        }
    )


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
