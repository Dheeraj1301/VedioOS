"""Aggregate, secret-free reconciliation of ready file records and private storage."""

import base64


class StorageReconciliationError(Exception):
    pass


def reconcile_ready_files(files, client, bucket):
    report = {
        "checked": 0,
        "invalid_metadata": 0,
        "inaccessible": 0,
        "size_mismatch": 0,
        "checksum_missing": 0,
        "checksum_mismatch": 0,
    }
    for file in files:
        report["checked"] += 1
        if not file.storage_version or len(file.sha256) != 64:
            report["invalid_metadata"] += 1
            continue
        try:
            expected_checksum = base64.b64encode(bytes.fromhex(file.sha256)).decode("ascii")
        except ValueError:
            report["invalid_metadata"] += 1
            continue
        try:
            metadata = client.head_object(
                Bucket=bucket,
                Key=file.object_key,
                VersionId=file.storage_version,
                ChecksumMode="ENABLED",
            )
        except Exception:
            report["inaccessible"] += 1
            continue
        if metadata.get("ContentLength") != file.size_bytes:
            report["size_mismatch"] += 1
        stored_checksum = metadata.get("ChecksumSHA256")
        if not stored_checksum:
            report["checksum_missing"] += 1
        elif stored_checksum != expected_checksum:
            report["checksum_mismatch"] += 1

    failures = sum(value for key, value in report.items() if key != "checked")
    if failures:
        summary = ", ".join(
            f"{key}={value}" for key, value in report.items() if key != "checked" and value
        )
        raise StorageReconciliationError(
            f"Private storage reconciliation failed for {failures} check(s): {summary}. "
            "Client filenames and object keys were omitted."
        )
    return report
