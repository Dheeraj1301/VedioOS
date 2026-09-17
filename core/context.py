NAV = {
    "client": [
        ("Overview", "/client/"),
        ("New order", "/client/new-order/"),
        ("My projects", "/client/projects/"),
        ("Payment history", "/client/payments/"),
    ],
    "editor": [
        ("Assigned projects", "/editor/"),
        ("Project details", "/editor/projects/"),
        ("Revisions", "/editor/revisions/"),
        ("Wallet", "/editor/wallet/"),
        ("Availability", "/editor/availability/"),
    ],
    "admin": [
        ("Overview", "/admin/"),
        ("Orders", "/admin/orders/"),
        ("Projects", "/admin/projects/"),
        ("Editors", "/admin/editors/"),
        ("Clients", "/admin/clients/"),
        ("Assignments", "/admin/assignments/"),
        ("Plans / Pricing", "/admin/pricing/"),
        ("Calls", "/admin/calls/"),
        ("Payouts", "/admin/payouts/"),
        ("Analytics", "/admin/analytics/"),
    ],
}


def navigation(request):
    if not request.user.is_authenticated:
        return {}
    return {
        "navigation": [
            {"label": label, "url": url, "active": request.path == url}
            for label, url in NAV.get(request.user.role, []) + [("Notifications", "/orders/notifications/")]
        ]
    }
