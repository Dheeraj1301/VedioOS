from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.models import File
from core.storage import storage_client
from core.storage_reconciliation import StorageReconciliationError, reconcile_ready_files


class Command(BaseCommand):
    help = "Verify every ready file record against its exact private object version, size and checksum."

    def handle(self, *args, **options):
        if not settings.S3_ENDPOINT_URL or not settings.S3_BUCKET:
            raise CommandError("Private storage endpoint and bucket must be configured.")
        files = File.objects.filter(state="ready").only(
            "object_key", "storage_version", "size_bytes", "sha256"
        ).iterator(chunk_size=100)
        try:
            report = reconcile_ready_files(files, storage_client(), settings.S3_BUCKET)
        except StorageReconciliationError as exc:
            raise CommandError(str(exc)) from None
        self.stdout.write(
            self.style.SUCCESS(
                f"Private storage reconciliation passed for {report['checked']} ready file record(s): "
                "exact versions, sizes and checksums agree. No client filenames, object keys, "
                "credentials or signed URLs were printed."
            )
        )
