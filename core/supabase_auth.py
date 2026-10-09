"""Server-side Supabase Auth password verification and client provisioning."""

import uuid
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Client, User


class SupabaseAuthUnavailable(Exception):
    pass


class SupabaseAuthRejected(Exception):
    """A safe, non-secret reason returned by the Supabase Auth boundary."""

    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def _configuration():
    base_url = settings.SUPABASE_AUTH_URL.rstrip("/") + "/"
    key = settings.SUPABASE_AUTH_PUBLISHABLE_KEY
    if not settings.SUPABASE_AUTH_URL or not key:
        raise SupabaseAuthUnavailable("Supabase Auth is not configured.")
    return base_url, key


def _json(response):
    try:
        return response.json()
    except ValueError:
        return {}


def verify_password(email, password):
    """Return the verified Supabase identity without retaining its tokens."""
    base_url, key = _configuration()
    try:
        token_response = requests.post(
            urljoin(base_url, "auth/v1/token?grant_type=password"),
            json={"email": email, "password": password},
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            timeout=settings.SUPABASE_AUTH_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise SupabaseAuthUnavailable("Supabase Auth could not be reached.") from exc

    token_body = _json(token_response)
    error_code = str(
        token_body.get("error_code") or token_body.get("code") or ""
    ).strip().lower()
    if token_response.status_code == 429:
        raise SupabaseAuthRejected("rate_limited")
    if token_response.status_code in {400, 401, 403, 422}:
        if error_code == "email_not_confirmed":
            raise SupabaseAuthRejected("email_not_confirmed")
        return None
    if token_response.status_code != 200:
        raise SupabaseAuthUnavailable("Supabase Auth rejected the sign-in request.")

    access_token = token_body.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise SupabaseAuthUnavailable("Supabase Auth returned an incomplete session.")

    try:
        user_response = requests.get(
            urljoin(base_url, "auth/v1/user"),
            headers={"apikey": key, "Authorization": f"Bearer {access_token}"},
            timeout=settings.SUPABASE_AUTH_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise SupabaseAuthUnavailable("Supabase Auth could not validate the session.") from exc
    if user_response.status_code != 200:
        raise SupabaseAuthUnavailable("Supabase Auth could not validate the session.")

    auth_user = _json(user_response)
    confirmed_email = str(auth_user.get("email") or "").strip().lower()
    if confirmed_email != email.strip().lower():
        return None
    if not (auth_user.get("email_confirmed_at") or auth_user.get("confirmed_at")):
        return None
    try:
        auth_user_id = uuid.UUID(str(auth_user.get("id")))
    except (TypeError, ValueError, AttributeError):
        raise SupabaseAuthUnavailable("Supabase Auth returned an invalid identity.") from None
    return {"id": auth_user_id, "email": confirmed_email}


def _provision_client(identity):
    email = identity["email"]
    auth_user_id = identity["id"]
    with transaction.atomic():
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "name": email.partition("@")[0][:120],
                "role": User.Role.CLIENT,
                "is_active": True,
                "email_verified_at": timezone.now(),
                "supabase_auth_user_id": auth_user_id,
                "password": make_password(None),
            },
        )
        user = User.objects.select_for_update().get(pk=user.pk)
        if user.role != User.Role.CLIENT:
            return None
        if user.supabase_auth_user_id and user.supabase_auth_user_id != auth_user_id:
            return None
        conflicting_identity = User.objects.filter(
            supabase_auth_user_id=auth_user_id
        ).exclude(pk=user.pk)
        if conflicting_identity.exists():
            return None

        updates = []
        linked_now = False
        if not user.supabase_auth_user_id:
            user.supabase_auth_user_id = auth_user_id
            updates.append("supabase_auth_user_id")
            linked_now = True
        if not user.is_active:
            user.is_active = True
            updates.append("is_active")
        if user.email_verified_at is None:
            user.email_verified_at = timezone.now()
            updates.append("email_verified_at")
        if updates:
            user.save(update_fields=updates)
        Client.objects.get_or_create(user=user)

        if created or linked_now:
            from operations.models import AuditLog

            AuditLog.objects.create(
                actor=user,
                action=(
                    "client.supabase_auth_provisioned"
                    if created
                    else "client.supabase_auth_linked"
                ),
                target_id=str(user.pk),
                detail={"provider": "supabase_auth"},
            )
        return user


def authenticate_supabase_client(email, password):
    """Authenticate a confirmed Supabase user and return its application client."""
    if not settings.SUPABASE_AUTH_PASSWORD_LOGIN_ENABLED:
        return None
    normalized_email = str(email or "").strip().lower()
    if "@" not in normalized_email or not password:
        return None

    existing = User.objects.filter(email__iexact=normalized_email).first()
    if existing and existing.role != User.Role.CLIENT:
        return None
    identity = verify_password(normalized_email, password)
    if not identity:
        return None
    try:
        return _provision_client(identity)
    except IntegrityError:
        # A concurrent first login may win the unique-email insert. Re-read and
        # validate the resulting mapping rather than creating a second identity.
        user = User.objects.filter(email__iexact=normalized_email).first()
        if (
            user
            and user.role == User.Role.CLIENT
            and user.supabase_auth_user_id == identity["id"]
            and hasattr(user, "client_profile")
        ):
            return user
        return None
