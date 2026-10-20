"""Safely link an existing client profile to its confirmed Supabase Auth identity."""

import uuid
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.models import User
from operations.models import AuditLog


class Command(BaseCommand):
    help = (
        "Link one existing, unlinked client profile to the unique confirmed "
        "Supabase Auth user with the same email."
    )

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)

    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        user = User.objects.filter(email__iexact=email).select_related("client_profile").first()
        if not user or user.role != User.Role.CLIENT or not hasattr(user, "client_profile"):
            raise CommandError("An existing VedioOS client profile was not found.")

        secret_key = settings.SUPABASE_SECRET_KEY
        if not settings.SUPABASE_AUTH_URL or not secret_key:
            raise CommandError("Supabase Auth administrator access is not configured.")
        headers = {"apikey": secret_key, "Authorization": f"Bearer {secret_key}"}
        try:
            response = requests.get(
                urljoin(settings.SUPABASE_AUTH_URL.rstrip("/") + "/", "auth/v1/admin/users"),
                headers=headers,
                params={"page": 1, "per_page": 1000},
                timeout=settings.SUPABASE_AUTH_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            raise CommandError("Supabase Auth could not be reached.") from exc
        if response.status_code != 200:
            raise CommandError(
                f"Supabase Auth user lookup failed (HTTP {response.status_code})."
            )

        matches = [
            auth_user
            for auth_user in response.json().get("users", [])
            if str(auth_user.get("email") or "").strip().lower() == email
        ]
        if len(matches) != 1:
            raise CommandError("Expected exactly one Supabase Auth user with this email.")
        identity = matches[0]
        if not (identity.get("email_confirmed_at") or identity.get("confirmed_at")):
            raise CommandError("The matching Supabase Auth email is not confirmed.")
        try:
            auth_user_id = uuid.UUID(str(identity.get("id")))
        except (TypeError, ValueError, AttributeError):
            raise CommandError("Supabase Auth returned an invalid user ID.") from None

        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=user.pk)
            if user.supabase_auth_user_id and user.supabase_auth_user_id != auth_user_id:
                raise CommandError(
                    "The client is linked to a different Supabase identity; refusing to overwrite it."
                )
            conflict = User.objects.filter(supabase_auth_user_id=auth_user_id).exclude(pk=user.pk)
            if conflict.exists():
                raise CommandError("The Supabase identity is already linked to another user.")
            if user.supabase_auth_user_id == auth_user_id:
                self.stdout.write(self.style.SUCCESS("PASS: client identity is already reconciled"))
                return

            user.supabase_auth_user_id = auth_user_id
            update_fields = ["supabase_auth_user_id"]
            if user.email_verified_at is None:
                user.email_verified_at = timezone.now()
                update_fields.append("email_verified_at")
            user.save(update_fields=update_fields)
            AuditLog.objects.create(
                actor=user,
                action="client.supabase_auth_reconciled",
                target_id=str(user.pk),
                detail={"provider": "supabase_auth", "reason": "confirmed_identity_recreated"},
            )

        self.stdout.write(self.style.SUCCESS("PASS: client identity reconciled"))
