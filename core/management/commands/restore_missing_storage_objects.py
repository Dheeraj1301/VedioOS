import base64
import hashlib
import json
from pathlib import Path
from uuid import UUID

from botocore.exceptions import ClientError
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import File
from core.storage import storage_client
from operations.models import AuditLog


class Command(BaseCommand):
    help = "Validate recovered private files and optionally restore their exact bytes to storage."

    def add_arguments(self, parser):
        parser.add_argument("manifest", help="Ignored .runtime JSON recovery manifest.")
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--confirm-restore", action="store_true")

    def handle(self, *args, **options):
        if options["apply"] != options["confirm_restore"]:
            raise CommandError("Applying recovery requires --apply and --confirm-restore together.")
        runtime = (Path(settings.BASE_DIR) / ".runtime").resolve()
        manifest_path = Path(options["manifest"]).resolve()
        if runtime not in manifest_path.parents:
            raise CommandError("The recovery manifest must be inside ignored .runtime.")
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            entries = payload["files"]
        except (OSError, ValueError, KeyError, TypeError):
            raise CommandError("The recovery manifest is missing or invalid.") from None
        if not isinstance(entries, list) or not entries:
            raise CommandError("The recovery manifest must contain a nonempty files list.")

        requested = []
        identifiers = set()
        for entry in entries:
            try:
                file_id = UUID(str(entry["file_id"]))
                source = Path(entry["path"]).resolve(strict=True)
            except (KeyError, TypeError, ValueError, OSError):
                raise CommandError("A recovery manifest entry is invalid.") from None
            if file_id in identifiers or not source.is_file():
                raise CommandError("Recovery entries must identify unique files.")
            identifiers.add(file_id)
            requested.append((file_id, source))

        records = {item.pk: item for item in File.objects.filter(pk__in=identifiers)}
        if len(records) != len(identifiers):
            raise CommandError("A recovery record does not exist.")

        validated = []
        for file_id, source in requested:
            record = records[file_id]
            if record.state != "ready" or not record.storage_version:
                raise CommandError("Only ready immutable file records can be recovered.")
            size = source.stat().st_size
            digest = hashlib.sha256()
            with source.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            if size != record.size_bytes or digest.hexdigest() != record.sha256:
                raise CommandError("Recovered bytes do not match their stored size and checksum.")
            validated.append((record, source))

        if not options["apply"]:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Recovery dry run passed for {len(validated)} file(s); storage was unchanged."
                )
            )
            return

        client = storage_client()
        restored = 0
        for record, source in validated:
            try:
                client.head_object(
                    Bucket=settings.S3_BUCKET,
                    Key=record.object_key,
                    VersionId=record.storage_version,
                    ChecksumMode="ENABLED",
                )
            except ClientError as error:
                code = str(error.response.get("Error", {}).get("Code", ""))
                if code not in {"404", "NoSuchKey", "NoSuchVersion", "NotFound"}:
                    raise CommandError(
                        "Private storage could not verify a recovery target; no upload was attempted."
                    ) from None
            else:
                raise CommandError("A recovery target is already accessible; refusing to overwrite it.")

            checksum = base64.b64encode(bytes.fromhex(record.sha256)).decode("ascii")
            try:
                with source.open("rb") as handle:
                    response = client.put_object(
                        Bucket=settings.S3_BUCKET,
                        Key=record.object_key,
                        Body=handle,
                        ContentLength=record.size_bytes,
                        ContentType=record.content_type,
                        ChecksumSHA256=checksum,
                    )
                version = response.get("VersionId")
                if not version:
                    raise ValueError
                metadata = client.head_object(
                    Bucket=settings.S3_BUCKET,
                    Key=record.object_key,
                    VersionId=version,
                    ChecksumMode="ENABLED",
                )
                if (
                    metadata.get("ContentLength") != record.size_bytes
                    or metadata.get("ChecksumSHA256") != checksum
                ):
                    raise ValueError
            except Exception:
                raise CommandError(
                    f"Storage recovery stopped after {restored} verified file(s); private identifiers were omitted."
                ) from None

            with transaction.atomic():
                locked = File.objects.select_for_update().get(pk=record.pk)
                if locked.storage_version != record.storage_version or locked.state != "ready":
                    raise CommandError(
                        "A recovery record changed concurrently; the new unreferenced version requires review."
                    )
                locked.storage_version = version
                locked.save(update_fields=["storage_version", "updated_at"])
                AuditLog.objects.create(
                    actor=None,
                    action="file.storage_recovered",
                    target_id=str(locked.pk),
                    detail={"reason": "verified_backup_restore"},
                )
            restored += 1

        self.stdout.write(self.style.SUCCESS(f"Storage recovery completed for {restored} file(s)."))
