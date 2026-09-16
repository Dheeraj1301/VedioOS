from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.models import UploadPolicy


class Command(BaseCommand):
    help = "Initialize development-only upload configuration without prices or accounts."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Local configuration is only allowed with DEBUG=true.")
        _, created = UploadPolicy.objects.get_or_create(
            pk=1,
            defaults={
                "max_bytes": 536870912,
                "allowed_types": {
                    ".mp4": ["video/mp4"],
                    ".mov": ["video/quicktime"],
                    ".webm": ["video/webm"],
                    ".jpg": ["image/jpeg"],
                    ".jpeg": ["image/jpeg"],
                    ".png": ["image/png"],
                    ".mp3": ["audio/mpeg"],
                    ".wav": ["audio/wav", "audio/x-wav"],
                    ".pdf": ["application/pdf"],
                },
            },
        )
        self.stdout.write(
            "Created local 512 MiB upload policy." if created else "Existing upload policy preserved."
        )
