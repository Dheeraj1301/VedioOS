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


def landing_video_permission(config):
    params = {
        "Bucket": settings.S3_BUCKET,
        "Key": config.hero_video_object_key,
        "ResponseContentType": "video/mp4",
        "ResponseContentDisposition": "inline",
    }
    if config.hero_video_storage_version:
        params["VersionId"] = config.hero_video_storage_version
    return storage_client().generate_presigned_url(
        "get_object", Params=params, ExpiresIn=settings.DOWNLOAD_TTL_SECONDS
    )


def delete_private_object_versions(object_key):
    """Permanently delete every version and delete marker for one exact key."""
    client = storage_client()
    deleted = 0
    key_marker = None
    version_marker = None
    while True:
        request = {"Bucket": settings.S3_BUCKET, "Prefix": object_key}
        if key_marker:
            request["KeyMarker"] = key_marker
        if version_marker:
            request["VersionIdMarker"] = version_marker
        page = client.list_object_versions(**request)
        objects = [
            {"Key": item["Key"], "VersionId": item["VersionId"]}
            for group in ("Versions", "DeleteMarkers")
            for item in page.get(group, [])
            if item.get("Key") == object_key
        ]
        if objects:
            client.delete_objects(
                Bucket=settings.S3_BUCKET,
                Delete={"Objects": objects, "Quiet": True},
            )
            deleted += len(objects)
        if not page.get("IsTruncated"):
            return deleted
        key_marker = page.get("NextKeyMarker")
        version_marker = page.get("NextVersionIdMarker")
