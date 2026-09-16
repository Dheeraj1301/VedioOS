"""S3 transport only: media bytes travel between the browser and object storage."""

import base64
from functools import lru_cache
from urllib.parse import quote

import boto3
from botocore.config import Config
from django.conf import settings


@lru_cache(maxsize=1)
def storage_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        region_name=settings.S3_REGION,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            connect_timeout=5,
            read_timeout=15,
            retries={"max_attempts": 2},
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    )


def upload_permission(file):
    checksum = base64.b64encode(bytes.fromhex(file.sha256)).decode()
    headers = {"Content-Type": file.content_type, "x-amz-checksum-sha256": checksum, "If-None-Match": "*"}
    url = storage_client().generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.S3_BUCKET,
            "Key": file.object_key,
            "ContentType": file.content_type,
            "ContentLength": file.size_bytes,
            "ChecksumSHA256": checksum,
            "IfNoneMatch": "*",
        },
        ExpiresIn=settings.UPLOAD_TTL_SECONDS,
    )
    return {"url": url, "method": "PUT", "headers": headers}


def inspect_object(file):
    return storage_client().head_object(
        Bucket=settings.S3_BUCKET, Key=file.object_key, ChecksumMode="ENABLED"
    )


def download_permission(file):
    return storage_client().generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.S3_BUCKET,
            "Key": file.object_key,
            "VersionId": file.storage_version,
            "ResponseContentDisposition": "attachment; filename*=UTF-8''" + quote(file.filename),
            "ResponseContentType": "application/octet-stream",
        },
        ExpiresIn=settings.DOWNLOAD_TTL_SECONDS,
    )
