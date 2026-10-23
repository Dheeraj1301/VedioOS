from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from core.identity_cleanup import (
    SupabaseDeletionSyncUnavailable,
    active_supabase_auth_ids,
    archive_deleted_identity,
)
from core.models import User


class Command(BaseCommand):
    help = "Find linked local identities missing from Supabase Auth and optionally archive them."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        try:
            active_ids = active_supabase_auth_ids()
        except SupabaseDeletionSyncUnavailable as exc:
            raise CommandError(str(exc)) from None
        linked = User.objects.filter(
            supabase_auth_user_id__isnull=False,
            auth_deleted_at__isnull=True,
        ).values_list("id", "supabase_auth_user_id")
        missing_ids = [user_id for user_id, auth_id in linked if auth_id not in active_ids]
        if not options["apply"]:
            self.stdout.write(f"Missing linked Supabase identities: {len(missing_ids)}.")
            return
        archived = 0
        blocked = 0
        for user_id in missing_ids:
            try:
                archive_deleted_identity(user_id)
            except ValidationError:
                blocked += 1
            else:
                archived += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"Supabase deletion reconciliation archived={archived}, blocked={blocked}."
            )
        )
