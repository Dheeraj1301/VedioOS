"""Supabase Auth-backed client email verification."""

from urllib.parse import urljoin

import requests
from django.conf import settings


class VerificationCooldown(Exception):
    pass


class VerificationServiceUnavailable(Exception):
    pass


def _auth_configuration():
    base_url = settings.SUPABASE_AUTH_URL.rstrip("/") + "/"
    key = settings.SUPABASE_AUTH_PUBLISHABLE_KEY
    if not settings.SUPABASE_AUTH_URL or not key:
        raise VerificationServiceUnavailable("Supabase Auth is not configured.")
    return base_url, key


def _post(path, payload):
    base_url, key = _auth_configuration()
    try:
        response = requests.post(
            urljoin(base_url, path.lstrip("/")),
            json=payload,
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            timeout=settings.SUPABASE_AUTH_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise VerificationServiceUnavailable("Supabase Auth could not be reached.") from exc
    try:
        body = response.json()
    except ValueError:
        body = {}
    return response.status_code, body


def send_verification_email(email, *, enforce_cooldown=True):
    """Ask Supabase Auth to create and email an OTP for this address."""
    status, body = _post("auth/v1/otp", {"email": email, "create_user": True})
    if status in {200, 204}:
        return
    if status == 429 and enforce_cooldown:
        raise VerificationCooldown
    raise VerificationServiceUnavailable(
        f"Supabase Auth rejected the verification request ({body.get('code', 'request_failed')})."
    )


def check_verification_code(email, code):
    """Validate an email OTP with Supabase Auth and discard its returned session."""
    status, body = _post(
        "auth/v1/verify",
        {"email": email, "token": code, "type": "email"},
    )
    if status in {200, 201}:
        user = body.get("user") or {}
        confirmed_email = str(user.get("email") or "").strip().lower()
        return "verified" if confirmed_email == email.strip().lower() else "invalid"
    if status == 429:
        return "locked"
    if body.get("code") in {"otp_expired", "expired_token"}:
        return "expired"
    if status in {400, 401, 403, 422}:
        return "invalid"
    raise VerificationServiceUnavailable("Supabase Auth could not verify the email code.")
