from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from operations.notifications import dispatch_due, release_held


class Command(BaseCommand):
    help = "Dispatch due external notification deliveries when explicitly enabled."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument(
            "--release-held",
            action="store_true",
            help="Release older held notices before dispatch. Requires email delivery to be enabled.",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        if not 1 <= limit <= 1000:
            raise CommandError("--limit must be between 1 and 1000.")
        if options["release_held"] and not settings.NOTIFICATION_EMAIL_ENABLED:
            raise CommandError("Enable NOTIFICATION_EMAIL_ENABLED before releasing held notices.")
        released = release_held(limit) if options["release_held"] else 0
        deliveries = dispatch_due(limit)
        sent = sum(item.state == "sent" for item in deliveries)
        failed = sum(item.state == "failed" for item in deliveries)
        cancelled = sum(item.state == "cancelled" for item in deliveries)
        self.stdout.write(
            self.style.SUCCESS(
                f"Released {released}; processed {len(deliveries)} deliveries: "
                f"{sent} sent, {failed} retrying, {cancelled} cancelled."
            )
        )
