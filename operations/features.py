"""Central, read-only inventory of actual platform activation controls."""

from django.conf import settings

from core.models import CommercePolicy, UploadPolicy

from .models import AssignmentPolicy, EarningPolicy


def _state(enabled, configured=True):
    if not configured:
        return "Not configured"
    return "Enabled" if enabled else "Disabled"


def feature_controls():
    commerce = CommercePolicy.objects.filter(pk=1).first()
    assignment = AssignmentPolicy.objects.filter(pk=1).first()
    earnings = EarningPolicy.objects.filter(pk=1).first()
    upload = UploadPolicy.objects.filter(pk=1).first()
    quote_configured = bool(
        commerce
        and commerce.currency
        and commerce.terms
        and commerce.delivery_terms
        and commerce.refund_terms
        and commerce.tax_terms
    )
    manual_assignment_configured = bool(
        assignment
        and assignment.manual_pointer
        and assignment.matching
        and assignment.capacity_scope
        and assignment.roster_order
    )
    automatic_assignment_configured = bool(
        manual_assignment_configured
        and assignment.busy_strategy
        and assignment.queue_order
    )
    earning_configured = bool(
        earnings
        and earnings.rule == "fixed_whole_v1"
        and earnings.release_mode == "manual"
        and all(
            isinstance(amount, int) and amount > 0
            for amount in [
                earnings.plan_1_coins,
                earnings.plan_2_coins,
                earnings.plan_3_coins,
                earnings.custom_coins,
            ]
        )
    )
    rows = [
        {
            "name": "Client quotes",
            "state": _state(bool(commerce and commerce.quotes_enabled), quote_configured),
            "detail": "Requires complete server-owned pricing and commercial terms.",
            "url": "/admin/pricing/policy/",
        },
        {
            "name": "Review and acceptance",
            "state": _state(bool(commerce and commerce.review_rule)),
            "detail": "New orders snapshot the selected review rule.",
            "url": "/admin/pricing/policy/",
        },
        {
            "name": "Private uploads",
            "state": _state(bool(upload and upload.enabled), bool(upload)),
            "detail": "Technical type and size controls; commercial limits remain separate.",
            "url": None,
            "control": "Managed by deployment",
        },
        {
            "name": "Manual assignment",
            "state": _state(
                bool(assignment and assignment.manual_enabled), manual_assignment_configured
            ),
            "detail": "Uses configured eligibility, capacity and rotation rules.",
            "url": "/admin/assignments/policy/",
        },
        {
            "name": "Automatic assignment",
            "state": _state(
                bool(assignment and assignment.automatic_enabled), automatic_assignment_configured
            ),
            "detail": "Processes only verified paid projects when explicitly enabled.",
            "url": "/admin/assignments/policy/",
        },
        {
            "name": "Editor earnings",
            "state": _state(bool(earnings and earnings.enabled), earning_configured),
            "detail": "Applies only to prospective orders with snapshotted earning terms.",
            "url": "/admin/earnings/",
        },
        {
            "name": "Coin redemptions",
            "state": _state(
                bool(earnings and earnings.redemptions_enabled), earning_configured
            ),
            "detail": "Real transfer processing remains unavailable without an approved provider.",
            "url": "/admin/earnings/",
        },
        {
            "name": "Payment gateway",
            "state": "Development sandbox"
            if settings.DEBUG and settings.PAYMENT_MODE == "sandbox"
            else "Disabled",
            "detail": "Environment-controlled; the sandbox never represents real revenue.",
            "url": None,
        },
        {
            "name": "Payout processing",
            "state": "Development sandbox"
            if settings.DEBUG and settings.PAYOUT_MODE == "sandbox"
            else "Disabled",
            "detail": "Environment-controlled; no real transfer provider is configured.",
            "url": None,
        },
        {
            "name": "External notification email",
            "state": _state(settings.NOTIFICATION_EMAIL_ENABLED),
            "detail": "Environment-controlled; older held notices require explicit release.",
            "url": None,
        },
        {
            "name": "Monthly package sales",
            "state": "Locked pending D13",
            "detail": "Draft management is available; purchases and renewals remain closed.",
            "url": "/admin/pricing/",
        },
        {
            "name": "AI complexity classification",
            "state": "Locked pending D08",
            "detail": "Manual admin assessment remains available; no AI provider is connected.",
            "url": "/admin/assignments/",
        },
    ]
    return {"features": rows}
