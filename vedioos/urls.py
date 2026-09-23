from django.urls import path

from core import commerce_views as commerce
from core import views
from core.delivery_views import delivery_action, mark_notification_read, notifications
from core.message_views import message_post
from operations import assignment_views as assignments
from operations import audit_views, earning_views
from operations import views as ops

urlpatterns = [
    path("editor/wallet/", earning_views.wallet, name="wallet"),
    path("editor/wallet/redeem/", earning_views.redeem, name="redeem"),
    path("admin/earnings/", earning_views.earning_settings, name="earning_settings"),
    path("admin/payouts/", earning_views.payouts, name="payouts"),
    path("admin/payouts/action/", earning_views.earning_action, name="earning_action"),
    path("orders/notifications/", notifications, name="notifications"),
    path("orders/notifications/<uuid:notice_id>/read/", mark_notification_read, name="mark_notification_read"),
    path("orders/<uuid:project_id>/delivery/", delivery_action, name="delivery_action"),
    path("orders/<uuid:project_id>/messages/", message_post, name="message_post"),
    path("", views.landing, name="landing"),
    path("register/", views.register, name="register"),
    path("verify-email/", views.verification_pending, name="verification_pending"),
    path("verify-email/resend/", views.resend_verification, name="resend_verification"),
    path("verify-email/<str:token>/", views.verify_email, name="verify_email"),
    path("register/editor/", ops.editor_register, name="editor_register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("client/", views.client_dashboard, name="client_dashboard"),
    path("client/new-order/", views.new_order, name="new_order"),
    path("client/projects/", views.my_projects, name="my_projects"),
    path(
        "client/projects/<uuid:project_id>/", views.project_detail, {"area": "client"}, name="client_project"
    ),
    path("client/payments/", views.payment_history, name="payment_history"),
    path("client/projects/<uuid:project_id>/quote/", commerce.quote_page, name="quote_select"),
    path("api/custom-estimate/", commerce.estimate_custom, name="estimate_custom"),
    path(
        "client/projects/<uuid:project_id>/quotes/<uuid:quote_id>/",
        commerce.quote_review,
        name="quote_review",
    ),
    path("orders/<uuid:project_id>/", commerce.order_summary, name="order_summary"),
    path("orders/<uuid:project_id>/checkout/", commerce.checkout, name="checkout"),
    path("payments/<uuid:payment_id>/receipt/", commerce.payment_receipt, name="payment_receipt"),
    path("api/payments/sandbox/webhook/", commerce.sandbox_webhook),
    path("editor/", ops.editor_dashboard, name="editor_dashboard"),
    path(
        "editor/projects/<uuid:project_id>/", views.project_detail, {"area": "editor"}, name="editor_project"
    ),
    path("editor/<str:page>/", ops.editor_page),
    path("admin/", ops.admin_dashboard, name="admin_dashboard"),
    path("admin/audit/", audit_views.audit_timeline, name="audit_timeline"),
    path("admin/calls/<uuid:call_id>/action/", ops.call_action, name="call_action"),
    path("admin/assignments/", assignments.assignments, name="assignments"),
    path("admin/assignments/policy/", assignments.assignment_policy, name="assignment_policy"),
    path("admin/assignments/process/", assignments.run_queue, name="run_assignment_queue"),
    path("admin/assignments/<uuid:project_id>/", assignments.assignment_detail, name="assignment_detail"),
    path(
        "admin/editors/<uuid:editor_id>/operations/", assignments.editor_operations, name="editor_operations"
    ),
    path("admin/projects/<uuid:project_id>/", views.project_detail, {"area": "admin"}, name="admin_project"),
    path("admin/editors/<uuid:editor_id>/approve/", ops.approve_editor, name="approve_editor"),
    path("admin/pricing/", commerce.pricing, name="pricing"),
    path("admin/pricing/plans/<int:slot>/", commerce.catalog_edit, {"kind": "plan"}, name="plan_edit"),
    path("admin/pricing/services/new/", commerce.catalog_edit, {"kind": "service"}, name="service_new"),
    path("admin/pricing/packages/new/", commerce.catalog_edit, {"kind": "package"}, name="package_new"),
    path(
        "admin/pricing/services/<uuid:item_id>/",
        commerce.catalog_edit,
        {"kind": "service"},
        name="service_edit",
    ),
    path(
        "admin/pricing/packages/<uuid:item_id>/",
        commerce.catalog_edit,
        {"kind": "package"},
        name="package_edit",
    ),
    path("admin/pricing/policy/", commerce.catalog_edit, {"kind": "policy"}, name="policy_edit"),
    path("admin/<str:page>/", ops.admin_page),
    path("api/projects/<uuid:project_id>/", views.project_api),
    path("api/projects/<uuid:project_id>/uploads/", views.request_upload),
    path("api/files/<uuid:file_id>/complete/", views.complete_upload),
    path("api/files/<uuid:file_id>/download/", views.request_download),
    path("api/areas/<str:area>/", views.area_api),
]
handler403 = "core.views.forbidden"
handler404 = "core.views.not_found"
handler500 = "core.views.server_error"
