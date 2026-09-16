"""Exercise real PostgreSQL auth and permissions in a rolled-back transaction."""

import secrets
import uuid

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.test import Client as Browser

from core.models import User
from operations.models import Admin


class Command(BaseCommand):
    help = "Run reversible auth/project checks against the active PostgreSQL database."

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            raise CommandError("This check requires PostgreSQL.")
        prefix = uuid.uuid4().hex
        password = secrets.token_urlsafe(32)

        def require(condition, label):
            if not condition:
                raise CommandError(f"Failed: {label}")
            self.stdout.write(f"PASS: {label}")

        with transaction.atomic():
            client = Browser()
            email = f"verification-client-{prefix}@example.test"
            response = client.post(
                "/register/",
                {"name": "Verification client", "email": email, "password1": password, "password2": password},
            )
            require(response.status_code == 302, "client registration")
            require(client.get("/client/").status_code == 200, "client dashboard")
            require(client.get("/admin/").status_code == 403, "client denied admin access")
            require(client.get("/editor/").status_code == 403, "client denied editor access")
            response = client.post(
                "/client/new-order/", {"title": "Temporary connection check", "song_choice": "suggest"}
            )
            require(response.status_code == 302, "project draft persists in PostgreSQL")
            from core.models import Project

            project = Project.objects.get(client__user__email=email)
            client.post("/logout/")
            require(client.get("/api/areas/client/").status_code == 401, "logout invalidates session")
            require(
                client.post("/login/", {"username": email, "password": password}).status_code == 302,
                "client login",
            )

            editor = Browser()
            response = editor.post(
                "/register/editor/",
                {
                    "name": "Verification editor",
                    "email": f"verification-editor-{prefix}@example.test",
                    "password1": password,
                    "password2": password,
                    "phone": "0000000000",
                    "experience": "Synthetic validation",
                    "tools": "External editor",
                    "portfolio": "https://example.com",
                    "previous_work": "Synthetic sample",
                    "expertise": "Editing",
                    "availability": "offline",
                },
            )
            require(
                response.status_code == 302 and editor.get("/editor/").status_code == 200,
                "editor registration and dashboard",
            )
            require(
                editor.get(f"/api/projects/{project.pk}/").status_code == 404,
                "unassigned editor denied project access",
            )
            admin_user = User.objects.create_user(
                f"verification-admin-{prefix}@example.test", password, name="Verification admin", role="admin"
            )
            Admin.objects.create(user=admin_user)
            admin = Browser()
            require(
                admin.post("/login/", {"username": admin_user.email, "password": password}).status_code
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
