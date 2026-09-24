"""Synthetic private-storage round trip with mandatory cleanup."""

import base64
import hashlib
import secrets
import uuid
from urllib.parse import quote

import requests


class StoragePreflightError(Exception):
    pass


def _remove_probe(client, bucket, key):
    result = client.list_object_versions(Bucket=bucket, Prefix=key)
    versions = result.get("Versions", []) + result.get("DeleteMarkers", [])
    for version in versions:
        if version.get("Key") == key:
            client.delete_object(Bucket=bucket, Key=key, VersionId=version["VersionId"])
    remaining = client.list_object_versions(Bucket=bucket, Prefix=key)
    leftovers = remaining.get("Versions", []) + remaining.get("DeleteMarkers", [])
    if any(item.get("Key") == key for item in leftovers):
        raise StoragePreflightError("Synthetic storage object cleanup could not be verified.")


def check_private_storage(client, endpoint, bucket, download_ttl=60, payload=None):
    """Verify versioned private byte storage without touching application records."""
    payload = payload if payload is not None else secrets.token_bytes(128 * 1024)
    digest = hashlib.sha256(payload).digest()
    checksum = base64.b64encode(digest).decode("ascii")
    key = f"__vedioos_checks__/{uuid.uuid4()}.bin"
    probe_created = False
    try:
        versioning = client.get_bucket_versioning(Bucket=bucket)
        if versioning.get("Status") != "Enabled":
            raise StoragePreflightError("Private storage bucket versioning is not enabled.")
        uploaded = client.put_object(
            Bucket=bucket,
            Key=key,
            Body=payload,
            ContentType="application/octet-stream",
            ChecksumSHA256=checksum,
            IfNoneMatch="*",
        )
        probe_created = True
        version_id = uploaded.get("VersionId")
        if not version_id:
            raise StoragePreflightError("Private storage did not return an immutable object version.")
        metadata = client.head_object(
            Bucket=bucket, Key=key, VersionId=version_id, ChecksumMode="ENABLED"
        )
        if metadata.get("ContentLength") != len(payload):
            raise StoragePreflightError("Private storage reported an unexpected object size.")
        stored_checksum = metadata.get("ChecksumSHA256")
        if stored_checksum and stored_checksum != checksum:
            raise StoragePreflightError("Private storage reported a checksum mismatch.")

        signed_url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key, "VersionId": version_id},
            ExpiresIn=min(max(int(download_ttl), 1), 300),
        )
        signed = requests.get(signed_url, timeout=30)
        if signed.status_code != 200 or hashlib.sha256(signed.content).digest() != digest:
            raise StoragePreflightError("Signed private download did not preserve the uploaded bytes.")

        direct_url = f"{endpoint.rstrip('/')}/{quote(bucket)}/{quote(key, safe='/')}"
        direct = requests.get(direct_url, timeout=15)
        if direct.status_code not in {401, 403, 404}:
            raise StoragePreflightError("Storage allowed anonymous access to the synthetic object.")
        return {"bytes": len(payload), "versioned": True, "anonymous_status": direct.status_code}
    finally:
        if probe_created:
            _remove_probe(client, bucket, key)
