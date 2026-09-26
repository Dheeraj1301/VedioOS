"""Secret-free release evidence assembled from read-only operational checks."""

from django.conf import settings

from .account_reconciliation import account_reconciliation_report
from .assignment_reconciliation import assignment_reconciliation_report
from .audit_reconciliation import audit_reconciliation_report
from .commerce_reconciliation import commerce_reconciliation_report
from .database_security import database_security_report
from .delivery_reconciliation import delivery_reconciliation_report
from .earnings_reconciliation import earnings_reconciliation_report
from .health import database_ready
from .models import File
from .notification_reconciliation import notification_reconciliation_report
from .snapshot_integrity import verify_snapshot
from .storage import storage_client
from .storage_inventory import inventory_private_storage
from .storage_preflight import check_private_storage
from .storage_reconciliation import reconcile_ready_files
from .workflow_reconciliation import workflow_findings


def _latest_snapshot():
    runtime = (settings.BASE_DIR / ".runtime").resolve()
    candidates = sorted(runtime.glob("database-snapshot-*.json"), reverse=True)
    return next(
        (path for path in candidates if path.with_suffix(".json.sha256").exists()),
        None,
    )


def collect_release_evidence(*, active_storage=False):
    """Run aggregate checks without returning credentials, URLs or private identifiers."""
    checks = {}
    storage = None

    try:
        ready = database_ready()
        checks["database"] = {
            "status": "pass" if ready else "fail",
            "code": "ready" if ready else "migration_or_connectivity_check_failed",
        }
    except Exception:
        checks["database"] = {"status": "fail", "code": "database_check_failed"}

    try:
        checks["accounts"] = account_reconciliation_report()
    except Exception:
        checks["accounts"] = {"status": "fail", "code": "account_reconciliation_failed"}

    try:
        checks["assignments"] = assignment_reconciliation_report()
    except Exception:
        checks["assignments"] = {"status": "fail", "code": "assignment_reconciliation_failed"}

    try:
        checks["audit_history"] = audit_reconciliation_report()
    except Exception:
        checks["audit_history"] = {"status": "fail", "code": "audit_reconciliation_failed"}

    try:
        checks["notification_outbox"] = notification_reconciliation_report()
    except Exception:
        checks["notification_outbox"] = {
            "status": "fail",
            "code": "notification_outbox_failed",
        }

    try:
        checks["commerce"] = commerce_reconciliation_report()
    except Exception:
        checks["commerce"] = {"status": "fail", "code": "commerce_reconciliation_failed"}

    try:
        checks["delivery"] = delivery_reconciliation_report()
    except Exception:
        checks["delivery"] = {"status": "fail", "code": "delivery_reconciliation_failed"}

    try:
        checks["earnings"] = earnings_reconciliation_report()
    except Exception:
        checks["earnings"] = {"status": "fail", "code": "earnings_reconciliation_failed"}

    try:
        security = database_security_report()
        facts = security.pop("facts")
        checks["database_protection"] = {
            **security,
            "table_count": facts.get("table_count", 0),
            "extension_count": len(facts.get("extensions", [])),
        }
    except Exception:
        checks["database_protection"] = {
            "status": "fail",
            "code": "private_schema_check_failed",
        }

    try:
        findings = workflow_findings()
        inconsistent = sum(findings.values())
        checks["workflows"] = {
            "status": "pass" if inconsistent == 0 else "fail",
            "code": "consistent" if inconsistent == 0 else "inconsistent_records",
            "inconsistent_records": inconsistent,
        }
    except Exception:
        checks["workflows"] = {"status": "fail", "code": "workflow_check_failed"}

    if not settings.S3_ENDPOINT_URL or not settings.S3_BUCKET:
        checks["storage_records"] = {
            "status": "fail",
            "code": "storage_not_configured",
        }
        checks["storage_inventory"] = {
            "status": "fail",
            "code": "storage_not_configured",
        }
    else:
        try:
            files = File.objects.filter(state="ready").only(
                "object_key", "storage_version", "size_bytes", "sha256"
            ).iterator(chunk_size=100)
            storage = storage_client()
            storage_report = reconcile_ready_files(files, storage, settings.S3_BUCKET)
            checks["storage_records"] = {
                "status": "pass",
                "code": "consistent",
                "checked": storage_report["checked"],
            }
            inventory_files = File.objects.only("object_key", "storage_version", "state").iterator(
                chunk_size=100
            )
            inventory = inventory_private_storage(
                inventory_files, storage, settings.S3_BUCKET
            )
            checks["storage_inventory"] = inventory
        except Exception:
            checks["storage_records"] = {
                "status": "fail",
                "code": "storage_reconciliation_failed",
            }
            checks["storage_inventory"] = {
                "status": "fail",
                "code": "storage_inventory_failed",
            }

    snapshot = _latest_snapshot()
    if snapshot is None:
        checks["snapshot"] = {"status": "skipped", "code": "no_local_snapshot"}
    else:
        try:
            payload = verify_snapshot(snapshot)
            checks["snapshot"] = {
                "status": "pass",
                "code": "integrity_verified",
                "table_count": len(payload["tables"]),
                "row_count": sum(len(rows) for rows in payload["tables"].values()),
            }
        except (OSError, ValueError):
            checks["snapshot"] = {
                "status": "fail",
                "code": "snapshot_integrity_failed",
            }

    if not active_storage:
        checks["active_storage"] = {"status": "skipped", "code": "not_requested"}
    elif not settings.S3_ENDPOINT_URL or not settings.S3_BUCKET:
        checks["active_storage"] = {
            "status": "fail",
            "code": "storage_not_configured",
        }
    else:
        try:
            storage = storage or storage_client()
            result = check_private_storage(
                storage,
                settings.S3_ENDPOINT_URL,
                settings.S3_BUCKET,
                settings.DOWNLOAD_TTL_SECONDS,
            )
            checks["active_storage"] = {
                "status": "pass",
                "code": "round_trip_verified",
                "bytes": result["bytes"],
                "versioned": result["versioned"],
                "anonymous_access_denied": result["anonymous_status"] in {401, 403, 404},
            }
        except Exception:
            checks["active_storage"] = {
                "status": "fail",
                "code": "active_storage_check_failed",
            }

    required = [
        "database",
        "accounts",
        "assignments",
        "audit_history",
        "notification_outbox",
        "commerce",
        "delivery",
        "earnings",
        "database_protection",
        "workflows",
        "storage_records",
        "storage_inventory",
    ]
    selected = required + (["active_storage"] if active_storage else [])
    snapshot_failed = checks["snapshot"]["status"] == "fail"
    passed = all(checks[name]["status"] == "pass" for name in selected) and not snapshot_failed
    return {"status": "pass" if passed else "fail", "checks": checks}
