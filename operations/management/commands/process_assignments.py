from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from operations.assignments import process_queue


class Command(BaseCommand):
    help = "Process the durable paid-project queue under the configured assignment policy."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50)

    def handle(self, *args, **options):
        if not 1 <= options["limit"] <= 500:
            raise CommandError("Limit must be between 1 and 500.")
        try:
            assigned, waiting = process_queue(limit=options["limit"])
        except ValidationError as exc:
            raise CommandError(" ".join(exc.messages)) from None
        self.stdout.write(f"Assigned: {assigned}; waiting: {waiting}")
