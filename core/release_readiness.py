"""Production configuration audit without exposing credential values."""

from django.conf import settings

from operations.models import AssignmentPolicy, EarningPolicy

from .models import CommercePolicy, UploadPolicy

LOCAL_HOSTS = {"127.0.0.1", "localhost", "testserver", "[::1]"}
DEVELOPMENT_EMAIL_BACKENDS = {
    "django.core.mail.backends.console.EmailBackend",
    "django.core.mail.backends.locmem.EmailBackend",
    "django.core.mail.backends.dummy.EmailBackend",
}

MANUAL_GATES = [
    "D02 production storage, retention, scanning and recovery",
    "D03-D06 commercial terms, real payments and deadline policy",
    "D07-D12 assignment, AI, earnings, review and communication policy",
    "D13-D15 packages, public content and analytics formulas",
    "D16 monitoring, restore targets, incidents and account lifecycle",
    "Representative browser, accessibility, large-file and end-to-end release exercises",
]


def current_release_config():
    database = settings.DATABASES.get("default", {})
    return {
        "debug": settings.DEBUG,
        "secret_key": settings.SECRET_KEY,
        "allowed_hosts": settings.ALLOWED_HOSTS,
        "csrf_trusted_origins": getattr(settings, "CSRF_TRUSTED_ORIGINS", []),
        "database_engine": database.get("ENGINE", ""),
        "database_options": database.get("OPTIONS", {}),
        "storage_endpoint": settings.S3_ENDPOINT_URL,
        "storage_bucket": settings.S3_BUCKET,
        "supabase_auth_url": settings.SUPABASE_AUTH_URL,
        "supabase_auth_key_configured": bool(settings.SUPABASE_AUTH_PUBLISHABLE_KEY),
        "email_backend": settings.EMAIL_BACKEND,
        "default_from_email": settings.DEFAULT_FROM_EMAIL,
        "payment_mode": settings.PAYMENT_MODE,
        "payout_mode": settings.PAYOUT_MODE,
        "notification_email_enabled": settings.NOTIFICATION_EMAIL_ENABLED,
        "session_cookie_secure": settings.SESSION_COOKIE_SECURE,
        "csrf_cookie_secure": settings.CSRF_COOKIE_SECURE,
        "ssl_redirect": settings.SECURE_SSL_REDIRECT,
        "hsts_seconds": settings.SECURE_HSTS_SECONDS,
    }


def current_policy_state():
    commerce = CommercePolicy.objects.filter(pk=1).first()
    assignment = AssignmentPolicy.objects.filter(pk=1).first()
    earnings = EarningPolicy.objects.filter(pk=1).first()
    upload = UploadPolicy.objects.filter(pk=1).first()
    return {
        "quotes_enabled": bool(commerce and commerce.quotes_enabled),
        "pricing_context": commerce.pricing_context if commerce else "unconfigured",
        "automatic_assignment": bool(assignment and assignment.automatic_enabled),
        "earnings_enabled": bool(earnings and earnings.enabled),
        "redemptions_enabled": bool(earnings and earnings.redemptions_enabled),
        "uploads_enabled": bool(upload and upload.enabled),
    }


def release_findings(config, policies):
    findings = []

    def block(code, message):
        findings.append({"severity": "blocker", "code": code, "message": message})

    def warn(code, message):
        findings.append({"severity": "warning", "code": code, "message": message})

    if config["debug"]:
        block("debug_enabled", "DEBUG must be false.")
    if len(config["secret_key"]) < 50:
        block("weak_secret_key", "SECRET_KEY must be a high-entropy production value.")
    hosts = {host.strip().lower() for host in config["allowed_hosts"] if host.strip()}
    if not hosts or hosts <= LOCAL_HOSTS or "*" in hosts:
        block("allowed_hosts", "ALLOWED_HOSTS must contain explicit production hostnames.")
    if not config["csrf_trusted_origins"]:
        block("csrf_origins", "CSRF_TRUSTED_ORIGINS must contain the HTTPS production origin.")
    if not config["session_cookie_secure"]:
        block("session_cookie", "SESSION_COOKIE_SECURE must be enabled.")
    if not config["csrf_cookie_secure"]:
        block("csrf_cookie", "CSRF_COOKIE_SECURE must be enabled.")
    if not config["ssl_redirect"]:
        block("ssl_redirect", "SECURE_SSL_REDIRECT must be enabled.")
    if config["hsts_seconds"] < 31536000:
        block("hsts", "HSTS must be enabled for at least one year after HTTPS is verified.")
    if config["database_engine"] != "django.db.backends.postgresql":
        block("database_backend", "Production requires PostgreSQL.")
    database_options = config["database_options"] or {}
    if database_options.get("sslmode") != "verify-full" or not database_options.get("sslrootcert"):
        block("database_tls", "PostgreSQL must use verify-full TLS with a trusted CA file.")
    if not str(config["storage_endpoint"]).lower().startswith("https://"):
        block("storage_tls", "Private object storage must use HTTPS.")
    if not config["storage_bucket"]:
        block("storage_bucket", "A private production storage bucket is required.")
    if not str(config["supabase_auth_url"]).lower().startswith("https://") or not config[
        "supabase_auth_key_configured"
    ]:
        block("supabase_auth", "Configure the selected Supabase Auth project and publishable key.")
    if config["payment_mode"] in {"sandbox", "razorpay_test"}:
        block("payment_sandbox", "A test payment gateway cannot run in production.")
    if config["payout_mode"] == "sandbox":
        block("payout_sandbox", "The development payout sandbox cannot run in production.")
    if policies["quotes_enabled"] and config["payment_mode"] == "disabled":
        block("quotes_without_gateway", "Disable quotes or configure the approved payment adapter.")
    if policies["quotes_enabled"] and policies.get("pricing_context", "unconfigured") != "production":
        block("test_pricing", "Replace test-only quotation values with approved production pricing.")
    if policies["redemptions_enabled"] and config["payout_mode"] == "disabled":
        block("redemptions_without_provider", "Disable redemptions or configure the approved payout adapter.")
    if not policies["uploads_enabled"]:
        block("uploads_disabled", "A validated upload policy must be enabled.")
    if config["notification_email_enabled"] and config["email_backend"] in DEVELOPMENT_EMAIL_BACKENDS:
        block("notification_email_backend", "External notifications require a production email backend.")
    if config["notification_email_enabled"] and "localhost" in config["default_from_email"].lower():
        block("notification_sender_domain", "External notifications require an approved sender domain.")
    if config["payment_mode"] == "disabled":
        warn("payments_disabled", "Real checkout is unavailable in this release configuration.")
    if config["payout_mode"] == "disabled":
        warn("payouts_disabled", "Real editor payouts are unavailable in this release configuration.")
    if not config["notification_email_enabled"]:
        warn("notification_email_disabled", "External notification email is held; in-app notices remain available.")
    if not policies["automatic_assignment"]:
        warn("automatic_assignment_disabled", "Automatic assignment is disabled.")
    if not policies["earnings_enabled"]:
        warn("earnings_disabled", "Editor earning credits are disabled for new orders.")
    return findings
