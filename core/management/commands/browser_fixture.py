"""Create synthetic local browser-test accounts; never callable over HTTP."""

import json
import secrets
import uuid

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.models import Client, User
from operations.models import Admin, Editor, EditorAvailability, EditorCoins


class Command(BaseCommand):
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Browser fixtures are local-only.")
        password = secrets.token_urlsafe(24)
        run_id = uuid.uuid4().hex[:10]
        admin_email = f"browser-admin-{run_id}@example.test"
        admin_user = User.objects.create_user(
            admin_email, password, name="Test Studio Manager", role="admin"
        )
        Admin.objects.create(user=admin_user)
        client_email = f"browser-client-{run_id}@example.test"
        client_user = User.objects.create_user(
            client_email,
            password,
            name="Browser Test Creator",
            role="client",
            email_verified_at=timezone.now(),
        )
        Client.objects.create(user=client_user)
        editor_email = f"browser-editor-{run_id}@example.test"
        editor_user = User.objects.create_user(
            editor_email, password, name="Browser Test Editor", role="editor"
        )
        editor = Editor.objects.create(
            user=editor_user,
            phone="9876543210",
            experience="Three years of short-form editing",
            tools="DaVinci Resolve",
            portfolio="https://example.com/portfolio",
            previous_work="https://example.com/reel",
            expertise="Color and storytelling",
        )
        EditorAvailability.objects.create(editor=editor, status="available")
        EditorCoins.objects.create(editor=editor)
        destination = settings.BASE_DIR / ".runtime" / "browser-fixture.json"
        destination.write_text(
            json.dumps(
                {
                    "password": password,
                    "admin": {"email": admin_email},
                    "client": {"email": client_email},
                    "editor": {"email": editor_email, "login_id": editor.login_id},
                }
            ),
            encoding="utf-8",
        )
        self.stdout.write(
            "Created synthetic test accounts. Credentials saved in ignored .runtime/browser-fixture.json."
        )
