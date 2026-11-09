import logging
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.core.cache import cache
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect

from .identity_cleanup import SupabaseDeletionSyncUnavailable, synchronize_supabase_deletions
from .models import User

logger = logging.getLogger(__name__)


class SingleActiveSessionMiddleware:
    """Allow only the session key most recently approved by the account owner."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if user.is_authenticated and user.active_session_key:
            session_key = request.session.session_key
            if user.active_session_key != session_key:
                logout(request)
                if request.path.startswith("/api/"):
                    return JsonResponse(
                        {"error": "This account was signed in on another device."}, status=401
                    )
                messages.info(
                    request,
                    "You were signed out because this account was used to continue on another device.",
                )
                return redirect("/login/?session=ended")
        return self.get_response(request)


def content_security_policy(payment_checkout=False):
    """Allow only this site, the private store, Google Fonts and Razorpay checkout."""
    endpoint = urlsplit(settings.S3_ENDPOINT_URL)
    storage = (
        f"{endpoint.scheme}://{endpoint.netloc}"
        if settings.PRIVATE_STORAGE_ENABLED and endpoint.netloc
        else ""
    )
    # Razorpay's checkout script injects inline styles and loads its risk-detection bundle,
    # so only the two payment pages relax those two directives.
    checkout_scripts = "https://cdn.razorpay.com" if payment_checkout else ""
    checkout_styles = "'unsafe-inline'" if payment_checkout else ""
    directives = [
        ("default-src", "'self'"),
        # Client-side SHA-256 hashing uses a bundled WebAssembly module so originals can be
        # integrity-checked before upload. `wasm-unsafe-eval` permits only WebAssembly
        # compilation; it does not permit JavaScript eval(), unlike `unsafe-eval`.
        ("script-src", f"'self' 'wasm-unsafe-eval' https://checkout.razorpay.com {checkout_scripts}"),
        ("style-src", f"'self' https://fonts.googleapis.com {checkout_styles}"),
        ("font-src", "'self' https://fonts.gstatic.com"),
        ("img-src", f"'self' data: blob: {storage}"),
        ("media-src", f"'self' blob: {storage}"),
        ("connect-src", f"'self' {storage} https://api.razorpay.com https://lumberjack.razorpay.com"),
        ("frame-src", "https://checkout.razorpay.com https://api.razorpay.com"),
        ("frame-ancestors", "'none'"),
        ("form-action", "'self'"),
        ("base-uri", "'self'"),
        ("object-src", "'none'"),
    ]
    return "; ".join(" ".join(f"{name} {sources}".split()) for name, sources in directives)


class PrivateResponseMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.content_security_policy = content_security_policy()

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith(
            (
                "/client/",
                "/editor/",
                "/admin/",
                "/api/",
                "/orders/",
                "/payments/",
                "/login/",
                "/register/",
                "/verify-email/",
            )
        ):
            response["Cache-Control"] = "no-store, private"
            response["X-Robots-Tag"] = "noindex, nofollow"
        response.setdefault("Content-Security-Policy", self.content_security_policy)
        response["X-Content-Type-Options"] = "nosniff"
        response["Referrer-Policy"] = "same-origin"
        response["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response


# AuthenticationMiddleware precedes this class in settings, so request.user is available.
class SupabaseDeletionSyncMiddleware:
    """Fail closed before rendering Admin data that may contain deleted identities."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            settings.SUPABASE_DELETION_SYNC_ENABLED
            and request.path.startswith("/admin/")
            and request.user.is_authenticated
            and request.user.role == "admin"
        ):
            try:
                synchronize_supabase_deletions()
            except SupabaseDeletionSyncUnavailable:
                response = HttpResponse(
                    "Admin identity synchronization is temporarily unavailable. Please retry.",
                    status=503,
                )
                response["Retry-After"] = "30"
                return response
            if not User.objects.filter(
                pk=request.user.pk,
                is_active=True,
                auth_deleted_at__isnull=True,
            ).exists():
                logout(request)
                return redirect("/login/?account=removed")
        return self.get_response(request)


class VisitSweepMiddleware:
    """Run the reminder and unpaid-project sweep on ordinary page visits, at most every few minutes.

    This keeps editor deadline reminders and unpaid-project cleanup on time without an hourly scheduler.
    One sweep runs at a time (the assignment policy row is the lock); a failure never affects the page.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            settings.VISIT_SWEEP_ENABLED
            and request.method == "GET"
            and not request.path.startswith(("/static/", "/internal/"))
            and cache.add("visit-sweep", 1, settings.VISIT_SWEEP_INTERVAL_SECONDS)
        ):
            try:
                run_visit_sweep()
            except Exception:
                logger.exception("Visit sweep failed")
        return self.get_response(request)


def run_visit_sweep():
    from operations.editor_deadline import send_deadline_emails
    from operations.models import AssignmentPolicy

    from .project_storage import expire_unpaid_projects

    with transaction.atomic():
        if not AssignmentPolicy.objects.select_for_update(skip_locked=True).filter(pk=1).exists():
            return
        expire_unpaid_projects()
        send_deadline_emails()
