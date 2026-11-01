"""Estimate each project's S3 cost from the app's own records (sizes, storage time, authorised downloads)."""

from collections import Counter, defaultdict
from decimal import Decimal

from django.conf import settings
from django.db.models import Count, Max, Q
from django.utils import timezone

from core.models import File, Project, ProjectStorageCleanup, ProjectVersion
from core.project_storage import DELETABLE_STATUSES

from .models import AuditLog

BYTES_PER_GB = Decimal(10**9)
SECONDS_PER_MONTH = Decimal(30 * 24 * 3600)
CENT = Decimal("0.01")


def storage_cost_report(now=None):
    now = now or timezone.now()
    files = list(
        File.objects.filter(storage_version__gt="").only(
            "pk", "project_id", "size_bytes", "state", "completed_at", "created_at", "updated_at"
        )
    )
    downloads = Counter(
        {
            row["target_id"]: row["n"]
            for row in AuditLog.objects.filter(
                action="file.download_authorized", target_id__in=[str(file.pk) for file in files]
            )
            .values("target_id")
            .annotate(n=Count("id"))
        }
    )
    per_project = defaultdict(lambda: {"files": 0, "stored_now": 0, "byte_seconds": 0, "downloads": 0, "downloaded": 0})
    for file in files:
        row = per_project[file.project_id]
        start = file.completed_at or file.created_at
        end = file.updated_at if file.state == "removed" else now
        row["files"] += 1
        row["byte_seconds"] += file.size_bytes * max((end - start).total_seconds(), 0)
        if file.state != "removed":
            row["stored_now"] += file.size_bytes
        count = downloads.get(str(file.pk), 0)
        row["downloads"] += count
        row["downloaded"] += file.size_bytes * count

    completed = dict(
        ProjectVersion.objects.filter(accepted_at__isnull=False)
        .values_list("project_id")
        .annotate(done=Max("accepted_at"))
    )
    cleanups = dict(ProjectStorageCleanup.objects.values_list("project_id", "state"))
    projects = (
        Project.objects.filter(Q(pk__in=list(per_project)) | Q(archived_at__isnull=True))
        .select_related("client__user")
        .order_by("-created_at")[:300]
    )

    rows, totals = [], defaultdict(Decimal)
    for project in projects:
        usage = per_project.get(project.pk, {"files": 0, "stored_now": 0, "byte_seconds": 0, "downloads": 0, "downloaded": 0})
        storage = Decimal(usage["byte_seconds"]) / BYTES_PER_GB / SECONDS_PER_MONTH * settings.AWS_S3_STORAGE_USD_PER_GB_MONTH
        egress = Decimal(usage["downloaded"]) / BYTES_PER_GB * settings.AWS_S3_EGRESS_USD_PER_GB
        requests = (
            Decimal(usage["files"]) * settings.AWS_S3_PUT_USD_PER_1000
            + Decimal(usage["downloads"]) * settings.AWS_S3_GET_USD_PER_1000
        ) / 1000
        total = storage + egress + requests
        done_at = completed.get(project.pk)
        rows.append(
            {
                "project": project,
                "client": project.client.user.name or project.client.user.email,
                "status": project.get_status_display(),
                "completed_days": (now - done_at).days if done_at else None,
                "deleted": project.archived_at is not None,
                "cleanup_state": cleanups.get(project.pk, ""),
                "deletable": project.archived_at is None and project.status in DELETABLE_STATUSES,
                "files": usage["files"],
                "stored_mb": Decimal(usage["stored_now"]) / 10**6,
                "downloads": usage["downloads"],
                "downloaded_mb": Decimal(usage["downloaded"]) / 10**6,
                "storage_usd": storage.quantize(Decimal("0.0001")),
                "egress_usd": egress.quantize(Decimal("0.0001")),
                "total_usd": total.quantize(Decimal("0.0001")),
            }
        )
        totals["storage"] += storage
        totals["egress"] += egress
        totals["requests"] += requests
        totals["total"] += total
        totals["stored_mb"] += Decimal(usage["stored_now"]) / 10**6
    credits = settings.AWS_CREDITS_USD
    return {
        "rows": rows,
        "totals": {key: value.quantize(CENT) for key, value in totals.items()},
        "credits": credits.quantize(CENT) if credits else None,
        "credits_left": (credits - totals["total"]).quantize(CENT) if credits else None,
        "rates": {
            "storage": settings.AWS_S3_STORAGE_USD_PER_GB_MONTH,
            "egress": settings.AWS_S3_EGRESS_USD_PER_GB,
            "put": settings.AWS_S3_PUT_USD_PER_1000,
            "get": settings.AWS_S3_GET_USD_PER_1000,
        },
        "generated_at": now,
    }
