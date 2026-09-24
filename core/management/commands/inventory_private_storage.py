import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.models import File
from core.storage import storage_client
from core.storage_inventory import inventory_private_storage


class Command(BaseCommand):
    help = "Compare private bucket versions with database references without printing object names."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", dest="as_json")
        parser.add_argument("--report-only", action="store_true")

    def handle(self, *args, **options):
        if not settings.S3_ENDPOINT_URL or not settings.S3_BUCKET:
            raise CommandError("Private storage endpoint and bucket must be configured.")
        files = File.objects.only("object_key", "storage_version", "state").iterator(chunk_size=100)
        try:
            report = inventory_private_storage(files, storage_client(), settings.S3_BUCKET)
        except Exception:
            raise CommandError(
                "Private storage inventory failed; credentials, filenames and object keys were omitted."
            ) from None
        if options["as_json"]:
            self.stdout.write(json.dumps(report, sort_keys=True))
        else:
            self.stdout.write(
                "Private storage inventory: "
                f"database references={report['database_references']}, "
                f"objects={report['bucket_objects']}, versions={report['bucket_versions']}, "
                f"pending reservations={report['pending_records']}."
            )
            self.stdout.write(
                "Critical findings: "
                f"ready without version={report['ready_without_version']}, "
                f"missing references={report['missing_referenced_versions']}, "
                f"synthetic probe artifacts={report['probe_artifacts']}."
            )
            self.stdout.write(
                "Retention-policy warnings: "
                f"unreferenced versions={report['unreferenced_versions']}, "
                f"delete markers={report['delete_markers']}."
            )
            self.stdout.write(f"Overall: {report['status'].upper()}")
        if report["status"] != "pass" and not options["report_only"]:
            raise CommandError(
                "Private storage inventory contains critical findings. No private identifiers were printed."
            )
