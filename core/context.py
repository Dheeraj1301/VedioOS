NAV = {
    "client": [
        ("Overview", "/client/"),
        ("Plan a new edit", "/client/new-order/"),
        ("My projects", "/client/projects/"),
        ("Payment history", "/client/payments/"),
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
        ("Projects", "/admin/projects/"),
        ("Editors", "/admin/editors/"),
        ("Clients", "/admin/clients/"),
        ("Assignments", "/admin/assignments/"),
        ("Plans / Pricing", "/admin/pricing/"),
        ("Calls", "/admin/calls/"),
        ("Payouts", "/admin/payouts/"),
        ("Support", "/admin/support/"),
        ("Audit", "/admin/audit/"),
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
