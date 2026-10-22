NAV = {
    "client": [
        ("Overview", "/client/"),
        ("Plan a new edit", "/client/new-order/"),
        ("My projects", "/client/projects/"),
        ("Payment history", "/client/payments/"),
        ("Project Communication", "/client/communication/"),
        ("Support", "/client/support/"),
    ],
    "editor": [
        ("Assigned projects", "/editor/"),
        ("Project details", "/editor/projects/"),
        ("Revisions", "/editor/revisions/"),
        ("Calls", "/editor/calls/"),
        ("Wallet", "/editor/wallet/"),
        ("Availability", "/editor/availability/"),
    ],
    "admin": [
        ("Overview", "/admin/"),
        ("Orders", "/admin/orders/"),
        ("Payments", "/admin/payments/"),
        ("Editors", "/admin/editors/"),
        ("Clients", "/admin/clients/"),
        ("Assignments", "/admin/assignments/"),
        ("Plans / Pricing", "/admin/pricing/"),
        ("Landing page", "/admin/landing-page/"),
        ("Feature controls", "/admin/features/"),
        ("Payouts", "/admin/payouts/"),
        ("Support", "/admin/support/"),
        ("Analytics", "/admin/analytics/"),
    ],
}


def navigation(request):
    if not request.user.is_authenticated:
        return {}
    return {
        "navigation": [
            {
                "label": label,
                "url": url,
                "active": request.path == url
                or (url == "/client/communication/" and request.path.startswith(url)),
            }
            for label, url in NAV.get(request.user.role, [])
        ]
    }


def notification_menu(request):
    if not request.user.is_authenticated:
        return {}
    from django.db.models import Q

    from operations.models import Notification, NotificationCampaign

    from .permissions import visible_projects

    notices = (
        Notification.objects.filter(recipient=request.user)
        .filter(Q(project__isnull=True) | Q(project__in=visible_projects(request.user)))
        .filter(Q(campaign__isnull=True) | Q(campaign__status=NotificationCampaign.Status.PUBLISHED))
        .select_related("campaign", "project")
        .order_by("-created_at", "-id")
    )
    menu_items = [] if request.path == "/orders/notifications/" else notices[:10]
    return {
        "notification_menu_items": menu_items,
        "notification_unread_count": notices.filter(read_at__isnull=True).count(),
    }
