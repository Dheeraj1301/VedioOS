from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .commerce import accept_quote, check_policy, create_quote
from .commerce_forms import PlanForm, PolicyForm, QuoteSelectionForm, ServiceForm
from .models import CommercePolicy, CustomService, OrderQuote, Payment, Plan
from .payments import apply_sandbox_event, sandbox_enabled, start_checkout
from .permissions import project_for, role_required
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
            "policy": CommercePolicy.objects.filter(pk=1).first() or CommercePolicy(),
        },
    )


@role_required("admin")
def catalog_edit(request, kind, slot=None, item_id=None):
    if kind == "plan":
        if slot not in [1, 2, 3]:
            raise PermissionDenied
        instance = Plan.objects.filter(slot=slot).first() or Plan(slot=slot)
        form_class, title = PlanForm, f"Plan {slot}"
    elif kind == "service":
        instance = get_object_or_404(CustomService, pk=item_id) if item_id else CustomService()
        form_class, title = ServiceForm, "Custom service"
    else:
        instance = CommercePolicy.objects.filter(pk=1).first() or CommercePolicy(pk=1)
        form_class, title = PolicyForm, "Commercial terms & custom pricing"
    form = form_class(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                item = form.save()
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
        }
    form = QuoteSelectionForm(
        request.POST or None,
        currency=policy.currency if policy else "",
        initial=initial,
    )
    if request.method == "POST":
        if set(request.POST) - {"csrfmiddlewaretoken", "kind", "plan", "services", "scope_confirmed"}:
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
                    form.cleaned_data["plan"].pk if form.cleaned_data["plan"] else None,
                    [item.pk for item in form.cleaned_data["services"]],
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
