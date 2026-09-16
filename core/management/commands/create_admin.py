from getpass import getpass

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import User
from core.views import audit
from operations.models import Admin


class Command(BaseCommand):
    help = "Provision an admin using a hidden password prompt; no public admin signup."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--name", required=True)

    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise CommandError("Account already exists; this command never silently elevates users.")
        password = getpass("Admin password: ")
        if password != getpass("Confirm password: "):
            raise CommandError("Passwords do not match.")
        try:
            validate_password(password, User(email=email, name=options["name"]))
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages)) from exc
        with transaction.atomic():
            user = User.objects.create_user(email, password, name=options["name"], role="admin")
            Admin.objects.create(user=user)
            audit(user, "admin.provisioned", user.id)
        self.stdout.write(self.style.SUCCESS("Admin created. Sign in through /login/."))
