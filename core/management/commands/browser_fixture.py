"""Create synthetic local browser-test accounts; never callable over HTTP."""

import json
import secrets
import uuid

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.models import User
from operations.models import Admin


class Command(BaseCommand):
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Browser fixtures are local-only.")
        password = secrets.token_urlsafe(24)
        email = f"browser-admin-{uuid.uuid4().hex[:10]}@example.test"
        user = User.objects.create_user(email, password, name="Test Studio Manager", role="admin")
        Admin.objects.create(user=user)
        destination = settings.BASE_DIR / ".runtime" / "browser-fixture.json"
        destination.write_text(json.dumps({"email": email, "password": password}), encoding="utf-8")
        self.stdout.write(
            "Created synthetic test admin. Credentials saved in ignored .runtime/browser-fixture.json."
        )
