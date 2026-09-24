from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.storage import storage_client
from core.storage_preflight import StoragePreflightError, check_private_storage


class Command(BaseCommand):
    help = "Round-trip synthetic bytes through configured private storage and remove every test version."

    def handle(self, *args, **options):
        if not settings.S3_ENDPOINT_URL or not settings.S3_BUCKET:
            raise CommandError("Private storage endpoint and bucket must be configured.")
        try:
            result = check_private_storage(
                storage_client(),
                settings.S3_ENDPOINT_URL,
                settings.S3_BUCKET,
                settings.DOWNLOAD_TTL_SECONDS,
            )
        except StoragePreflightError as exc:
            raise CommandError(str(exc)) from None
        except Exception as exc:
            raise CommandError(
                f"Private storage preflight failed with {exc.__class__.__name__}; no credentials or "
                "signed URLs were printed. Verify provider health and confirm synthetic-object cleanup."
            ) from None
        self.stdout.write(
            self.style.SUCCESS(
                f"Private storage preflight passed: {result['bytes']} synthetic bytes round-tripped "
                "through an immutable version; anonymous access was denied; all probe versions were "
                "removed."
            )
        )
