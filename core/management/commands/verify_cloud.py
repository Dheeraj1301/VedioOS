"""Exercise current auth and project permissions in one rolled-back transaction."""

import secrets
import uuid

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.test import Client as Browser
from django.test.utils import override_settings
from django.urls import reverse

from core.email_verification import verification_token
from core.models import Project, User
from operations.models import Admin, Editor, EditorAvailability, EditorCoins


def run_cloud_checks(write):
    """Run the reversible checks; kept separate so the current flow is testable on SQLite."""
    prefix = uuid.uuid4().hex
    password = f"Cloud-{secrets.token_hex(24)}-A7!"

    def require(condition, label):
        if not condition:
            raise CommandError(f"Failed: {label}")
        write(f"PASS: {label}")

    with override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
        with transaction.atomic():
            client = Browser()
            email = f"verification-client-{prefix}@example.test"
            response = client.post(
                "/register/",
                {
                    "name": "Verification client",
                    "email": email,
                    "password1": password,
                    "password2": password,
                },
            )
            require(
                response.status_code == 302 and response.url == reverse("verification_pending"),
                "client registration awaits email verification",
            )
            client_user = User.objects.get(email=email)
            require(
                not client_user.is_active and client_user.email_verified_at is None,
                "unverified client cannot start a session",
            )
            blocked_login = client.post("/login/", {"username": email, "password": password})
            require(
                blocked_login.status_code == 200 and not client.session.get("_auth_user_id"),
                "unverified client login is rejected",
            )
            verification = client.get(
                reverse("verify_email", args=[verification_token(client_user)])
            )
            require(
                verification.status_code == 302 and verification.url == reverse("client_dashboard"),
                "client email verification activates account",
            )
            require(client.get("/client/").status_code == 200, "client dashboard")
            require(client.get("/admin/").status_code == 403, "client denied admin access")
            require(client.get("/editor/").status_code == 403, "client denied editor access")
            response = client.post(
                "/client/new-order/",
                {
                    "title": "Temporary connection check",
                    "order_choice": "custom",
                    "reel_duration": "20_30",
                    "song_choice": "suggest",
                },
            )
            require(response.status_code == 302, "project draft persists in PostgreSQL")
            project = Project.objects.get(client__user__email=email)
            session_key = client.session.session_key
            require(client.post("/logout/").status_code == 302, "client logout")
            from django.contrib.sessions.models import Session

            require(
                not Session.objects.filter(session_key=session_key).exists(),
                "logout invalidates server session",
            )
            require(client.get("/api/areas/client/").status_code == 401, "anonymous API denied")
            require(
                client.post("/login/", {"username": email, "password": password}).status_code == 302,
                "verified client login",
            )

            public_editor = Browser()
            response = public_editor.get("/register/editor/")
            require(
                response.status_code == 302 and response.url == reverse("login"),
                "public editor registration is disabled",
            )
            editor_user = User.objects.create_user(
                f"verification-editor-{prefix}@example.test",
                password,
                name="Verification editor",
                role="editor",
            )
            editor_record = Editor.objects.create(
                user=editor_user,
                phone="",
                experience="",
                tools="",
                portfolio="",
                previous_work="",
                expertise="",
            )
            EditorAvailability.objects.create(editor=editor_record, status="offline")
            EditorCoins.objects.create(editor=editor_record)
            editor = Browser()
            require(
                editor.post(
                    "/login/", {"username": editor_record.login_id, "password": password}
                ).status_code
                == 302,
                "administrator-issued editor ID login",
            )
            require(editor.get("/editor/").status_code == 200, "editor dashboard")
            require(
                editor.get(f"/api/projects/{project.pk}/").status_code == 404,
                "unassigned editor denied project access",
            )

            admin_user = User.objects.create_user(
                f"verification-admin-{prefix}@example.test",
                password,
                name="Verification admin",
                role="admin",
            )
            Admin.objects.create(user=admin_user)
            admin = Browser()
            require(
                admin.post(
                    "/login/", {"username": admin_user.email, "password": password}
                ).status_code
                == 302,
                "admin login",
            )
            require(admin.get("/admin/").status_code == 200, "admin dashboard")
            require(
                admin.get(f"/api/projects/{project.pk}/").status_code == 200,
                "admin authorized project access",
            )
            transaction.set_rollback(True)
    require(not User.objects.filter(email__contains=prefix).exists(), "verification data rolled back")


class Command(BaseCommand):
    help = "Run reversible current auth/project checks against the active PostgreSQL database."

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            raise CommandError("This check requires PostgreSQL.")
        run_cloud_checks(self.stdout.write)
