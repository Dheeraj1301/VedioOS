import uuid

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from core.models import DeliveryAcceptance
from core.permissions import role_required
from core.views import audit

from .earning_forms import EarningPolicyForm, RedemptionForm
from .earnings import decide_redemption, release_earning, request_redemption, totals, wallet_for
from .models import CoinTransaction, EarningPolicy, RedemptionRequest


@role_required("editor")
def wallet(request):
    editor = request.user.editor_profile
    account = wallet_for(editor)
    policy = EarningPolicy.objects.filter(pk=1).first()
    return render(
        request,
        "operations/wallet.html",
        {
            "title": "Wallet",
            "totals": totals(account),
            "transactions": CoinTransaction.objects.filter(wallet=account).order_by("-created_at")[:100],
            "redemptions": account.redemptions.order_by("-created_at")[:100],
            "unpriced_acceptances": DeliveryAcceptance.objects.filter(
                assignment__editor=editor, earning_status="pending_policy"
            ).count(),
            "can_redeem": bool(
                policy
                and policy.enabled
                and policy.redemptions_enabled
                and settings.DEBUG
                and getattr(settings, "PAYOUT_MODE", "disabled") == "sandbox"
            ),
            "minimum": policy.redemption_minimum if policy else None,
            "form": RedemptionForm(),
            "request_key": uuid.uuid4(),
        },
    )


@require_POST
@role_required("editor")
def redeem(request):
    form = RedemptionForm(request.POST)
    if form.is_valid():
        try:
            request_redemption(request.user, form.cleaned_data["amount"], request.POST.get("request_key"))
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            messages.success(request, "Sandbox redemption requested; coins are reserved pending review.")
    else:
        messages.error(request, "Enter a valid whole-coin amount.")
    return redirect("wallet")


@role_required("admin")
def earning_settings(request):
    policy = EarningPolicy.objects.get(pk=1)
    form = EarningPolicyForm(request.POST or None, instance=policy)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            EarningPolicy.objects.select_for_update().get(pk=1)
            policy = form.save()
            audit(
                request.user,
                "earning.policy_saved",
                policy.pk,
                {
                    "enabled": policy.enabled,
                    "rule": policy.rule,
                    "redemptions_enabled": policy.redemptions_enabled,
                },
            )
        messages.success(request, "Saved. Only new quotes receive this earning rule.")
        return redirect("earning_settings")
    return render(request, "operations/earning_settings.html", {"title": "Earning settings", "form": form})


@role_required("admin")
def payouts(request):
    return render(
        request,
        "operations/payouts.html",
        {
            "title": "Payouts",
            "pending_earnings": DeliveryAcceptance.objects.filter(earning_status="pending_release")
            .select_related("assignment__editor__user", "project")
            .order_by("created_at")[:100],
            "requests": RedemptionRequest.objects.select_related("wallet__editor__user").order_by(
                "-created_at"
            )[:100],
            "sandbox": settings.DEBUG and getattr(settings, "PAYOUT_MODE", "disabled") == "sandbox",
        },
    )


@require_POST
@role_required("admin")
def earning_action(request):
    action = request.POST.get("action")
    try:
        if action == "release":
            release_earning(request.user, request.POST.get("id"))
        elif action in {"paid", "failed", "rejected"}:
            decide_redemption(
                request.user,
                request.POST.get("id"),
                action,
                request.POST.get("reference", ""),
                request.POST.get("reason", ""),
            )
        else:
            raise PermissionDenied
    except (ValidationError, ValueError, IntegrityError) as exc:
        messages.error(
            request, " ".join(exc.messages) if isinstance(exc, ValidationError) else "Invalid or duplicate request."
        )
    else:
        messages.success(request, "Earning or redemption updated.")
    return redirect("payouts")
