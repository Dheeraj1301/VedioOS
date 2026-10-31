from urllib.parse import urlsplit

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect

from .identity_cleanup import SupabaseDeletionSyncUnavailable, synchronize_supabase_deletions
from .models import User


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


def content_security_policy():
    """Allow only this site, the private store, Google Fonts and Razorpay checkout."""
    endpoint = urlsplit(settings.S3_ENDPOINT_URL)
    storage = (
        f"{endpoint.scheme}://{endpoint.netloc}"
        if settings.PRIVATE_STORAGE_ENABLED and endpoint.netloc
        else ""
    )
    directives = [
        ("default-src", "'self'"),
        ("script-src", "'self' https://checkout.razorpay.com"),
        ("style-src", "'self' https://fonts.googleapis.com"),
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
