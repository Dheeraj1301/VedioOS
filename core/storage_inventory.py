"""Aggregate database-to-bucket inventory without exposing private object names."""


def inventory_private_storage(files, client, bucket):
    references = set()
    ready_without_version = 0
    pending_records = 0
    for file in files:
        if file.state == "pending":
            pending_records += 1
        if file.state == "ready" and not file.storage_version:
            ready_without_version += 1
        if file.storage_version:
            references.add((file.object_key, file.storage_version))

    seen_versions = set()
    object_keys = set()
    delete_markers = 0
    probe_artifacts = 0
    key_marker = None
    version_marker = None
    while True:
        request = {"Bucket": bucket}
        if key_marker:
            request["KeyMarker"] = key_marker
        if version_marker:
            request["VersionIdMarker"] = version_marker
        page = client.list_object_versions(**request)
        for version in page.get("Versions", []):
            key = version.get("Key", "")
            version_id = version.get("VersionId", "")
            if key and version_id:
                object_keys.add(key)
                seen_versions.add((key, version_id))
            if key.startswith("__vedioos_checks__/"):
                probe_artifacts += 1
        for marker in page.get("DeleteMarkers", []):
            key = marker.get("Key", "")
            delete_markers += 1
            if key:
                object_keys.add(key)
            if key.startswith("__vedioos_checks__/"):
                probe_artifacts += 1
        if not page.get("IsTruncated"):
            break
        next_key = page.get("NextKeyMarker")
        next_version = page.get("NextVersionIdMarker")
        if not next_key or (next_key, next_version) == (key_marker, version_marker):
            raise ValueError("Private storage returned invalid inventory pagination markers.")
        key_marker, version_marker = next_key, next_version

    missing_referenced_versions = len(references - seen_versions)
    unreferenced_versions = len(seen_versions - references)
    critical = ready_without_version + missing_referenced_versions + probe_artifacts
    warnings = unreferenced_versions + delete_markers
    return {
        "status": "pass" if critical == 0 else "fail",
        "code": "inventory_consistent" if critical == 0 else "storage_inventory_failed",
        "database_references": len(references),
        "bucket_objects": len(object_keys),
        "bucket_versions": len(seen_versions),
        "ready_without_version": ready_without_version,
        "missing_referenced_versions": missing_referenced_versions,
        "probe_artifacts": probe_artifacts,
        "unreferenced_versions": unreferenced_versions,
        "delete_markers": delete_markers,
        "pending_records": pending_records,
        "warning_count": warnings,
    }
