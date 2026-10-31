from django.core.management.base import BaseCommand, CommandError

from core.models import AdminMFA, User
from core.views import audit


class Command(BaseCommand):
    help = "Remove an administrator's authenticator so they set it up again at next sign-in."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)

    def handle(self, *args, **options):
        user = User.objects.filter(email__iexact=options["email"].strip(), role=User.Role.ADMIN).first()
        if user is None:
            raise CommandError("No administrator has that email.")
        deleted, _ = AdminMFA.objects.filter(user=user).delete()
        audit(user, "account.mfa_reset", user.pk, {"source": "management_command"})
        self.stdout.write(
            self.style.SUCCESS("Authenticator removed; set-up is required at next sign-in.")
            if deleted
            else "No authenticator was set up for this administrator."
        )
