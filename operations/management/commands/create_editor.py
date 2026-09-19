from getpass import getpass

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import User
from core.views import audit
from operations.models import Editor, EditorAvailability, EditorCoins


class Command(BaseCommand):
    help = "Provision an editor ID and initial password; public editor signup is disabled."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--name", required=True)
        parser.add_argument("--editor-id")

    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        login_id = (options.get("editor_id") or "").strip().upper() or None
        if User.objects.filter(email__iexact=email).exists():
            raise CommandError("Account already exists.")
        if login_id and Editor.objects.filter(login_id__iexact=login_id).exists():
            raise CommandError("Editor ID already exists.")
        password = getpass("Initial editor password: ")
        if password != getpass("Confirm password: "):
            raise CommandError("Passwords do not match.")
        pending_user = User(email=email, name=options["name"], role="editor")
        try:
            validate_password(password, pending_user)
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages)) from exc
        with transaction.atomic():
            user = User.objects.create_user(email, password, name=options["name"], role="editor")
            editor = Editor.objects.create(
                user=user,
                **({"login_id": login_id} if login_id else {}),
                phone="",
                experience="",
                tools="",
                portfolio="",
                previous_work="",
                expertise="",
            )
            EditorAvailability.objects.create(editor=editor, status="offline")
            EditorCoins.objects.create(editor=editor)
            audit(user, "editor.provisioned", editor.id, {"login_id": editor.login_id})
        self.stdout.write(
            self.style.SUCCESS(f"Editor created with ID {editor.login_id}. Share credentials privately.")
        )
