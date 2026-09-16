from botocore.exceptions import ClientError
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.storage import storage_client


class Command(BaseCommand):
    help = "Create a private, versioned S3 bucket and local browser CORS rules."

    def add_arguments(self, parser):
        parser.add_argument("--origin", action="append", default=[])

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "This bootstrap is local-only. Provision production IAM/private storage separately."
            )
        client = storage_client()
        try:
            client.head_bucket(Bucket=settings.S3_BUCKET)
        except ClientError as exc:
            if exc.response["ResponseMetadata"]["HTTPStatusCode"] != 404:
                raise
            client.create_bucket(Bucket=settings.S3_BUCKET)
        client.put_bucket_versioning(Bucket=settings.S3_BUCKET, VersioningConfiguration={"Status": "Enabled"})
        client.put_bucket_cors(
            Bucket=settings.S3_BUCKET,
            CORSConfiguration={
                "CORSRules": [
                    {
                        "AllowedOrigins": options["origin"]
                        or ["http://127.0.0.1:8000", "http://localhost:8000"],
                        "AllowedMethods": ["PUT", "GET", "HEAD"],
                        "AllowedHeaders": ["content-type", "x-amz-checksum-sha256", "if-none-match"],
                        "ExposeHeaders": ["ETag"],
                        "MaxAgeSeconds": 300,
                    }
                ]
            },
        )
        self.stdout.write(self.style.SUCCESS("Private bucket initialized with versioning and browser CORS."))
