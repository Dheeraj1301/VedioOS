"""Secret-free release evidence assembled from read-only operational checks."""

from django.conf import settings
from django.db import connection

from .health import database_ready
from .models import File
from .snapshot_integrity import verify_snapshot
from .storage import storage_client
from .storage_preflight import check_private_storage
from .storage_reconciliation import reconcile_ready_files
from .workflow_reconciliation import workflow_findings


def _database_protection_evidence():
    if connection.vendor != "postgresql":
        return {"status": "fail", "code": "postgresql_required"}
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_schema()")
        schema = cursor.fetchone()[0]
        cursor.execute(
            "SELECT count(*), count(*) FILTER (WHERE NOT rowsecurity) "
            "FROM pg_tables WHERE schemaname = %s",
            [schema],
        )
        table_count, tables_without_rls = cursor.fetchone()
        cursor.execute(
            "SELECT rolname FROM pg_roles WHERE rolname IN ('anon', 'authenticated')"
        )
        browser_roles = {row[0] for row in cursor.fetchall()}
        browser_schema_access = False
        for role in browser_roles:
            cursor.execute("SELECT has_schema_privilege(%s, %s, 'USAGE')", [role, schema])
            browser_schema_access = browser_schema_access or cursor.fetchone()[0]
    passed = (
        schema == "vedioos"
        and table_count > 0
        and tables_without_rls == 0
        and browser_roles == {"anon", "authenticated"}
        and not browser_schema_access
    )
    return {
        "status": "pass" if passed else "fail",
        "code": "protected" if passed else "private_schema_check_failed",
        "table_count": table_count,
        "tables_without_rls": tables_without_rls,
        "browser_roles_without_schema_access": (
            len(browser_roles) if not browser_schema_access else 0
        ),
    }


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
        checks["database_protection"] = _database_protection_evidence()
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
        except Exception:
            checks["storage_records"] = {
                "status": "fail",
                "code": "storage_reconciliation_failed",
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

    required = ["database", "database_protection", "workflows", "storage_records"]
    selected = required + (["active_storage"] if active_storage else [])
    snapshot_failed = checks["snapshot"]["status"] == "fail"
    passed = all(checks[name]["status"] == "pass" for name in selected) and not snapshot_failed
    return {"status": "pass" if passed else "fail", "checks": checks}
