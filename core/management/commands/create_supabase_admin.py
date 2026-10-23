import uuid
from getpass import getpass
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.models import User
from core.views import audit
from operations.models import Admin


class Command(BaseCommand):
    help = "Provision a confirmed Supabase Auth identity and linked BRIO admin."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--name", required=True)

    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        name = options["name"].strip()
        if not name:
            raise CommandError("Name is required.")
        if User.objects.filter(email__iexact=email).exists():
            raise CommandError("Account already exists; this command never elevates users.")

        password = getpass("Admin password: ")
        if password != getpass("Confirm password: "):
            raise CommandError("Passwords do not match.")
        try:
            validate_password(password, User(email=email, name=name))
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages)) from exc

        base_url = settings.SUPABASE_AUTH_URL.rstrip("/") + "/"
        secret_key = settings.SUPABASE_SECRET_KEY
        if not base_url.strip("/") or not secret_key:
            raise CommandError("Supabase Auth URL and server-only secret key are required.")
        headers = {
            "apikey": secret_key,
            "Authorization": f"Bearer {secret_key}",
            "Content-Type": "application/json",
        }
        try:
            response = requests.post(
                urljoin(base_url, "auth/v1/admin/users"),
                headers=headers,
                json={
                    "email": email,
                    "password": password,
                    "email_confirm": True,
                    "user_metadata": {"name": name},
                },
                timeout=settings.SUPABASE_AUTH_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            raise CommandError("Supabase Auth could not be reached; no admin was created.") from exc
        if response.status_code not in {200, 201}:
            raise CommandError(
                f"Supabase Auth rejected admin creation (HTTP {response.status_code}); "
                "no application admin was created."
            )
        try:
            auth_user_id = uuid.UUID(str(response.json()["id"]))
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise CommandError("Supabase Auth returned an invalid identity.") from exc

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    email,
                    password,
                    name=name,
                    role=User.Role.ADMIN,
                    is_active=True,
                    email_verified_at=timezone.now(),
                    supabase_auth_user_id=auth_user_id,
                )
                Admin.objects.create(user=user)
                audit(
                    user,
                    "admin.provisioned",
                    user.id,
                    detail={"provider": "supabase_auth"},
                )
        except Exception as exc:
            try:
                rollback = requests.delete(
                    urljoin(base_url, f"auth/v1/admin/users/{auth_user_id}"),
                    headers=headers,
                    timeout=settings.SUPABASE_AUTH_TIMEOUT_SECONDS,
                )
                rollback.raise_for_status()
            except requests.RequestException as rollback_exc:
                raise CommandError(
                    "Application provisioning failed and the Supabase Auth rollback also failed; "
                    "inspect the Auth user before retrying."
                ) from rollback_exc
            raise CommandError(
                "Application provisioning failed; the new Supabase Auth identity was rolled back."
            ) from exc

        self.stdout.write(
            self.style.SUCCESS("Confirmed Supabase Auth identity and linked admin created.")
        )
