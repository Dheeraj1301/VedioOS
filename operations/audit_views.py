"""Admin-only audit timeline; never render raw detail payloads or signed URLs."""

from django.http import Http404
from django.shortcuts import render
from django.views.decorators.http import require_GET

from core.permissions import role_required

from .models import AuditLog


@require_GET
@role_required("admin")
def audit_timeline(request):
    before = request.GET.get("before")
    rows = AuditLog.objects.select_related("actor").order_by("-id")
    if before is not None:
        if not before.isascii() or not before.isdecimal() or not 1 <= len(before) <= 19:
            raise Http404("Invalid audit page.")
        cursor = int(before)
        if not 1 <= cursor <= 9223372036854775807:
            raise Http404("Invalid audit page.")
        rows = rows.filter(id__lt=cursor)
    batch = list(rows[:51])
    return render(
        request,
        "operations/audit.html",
        {
            "title": "Audit history",
            "events": batch[:50],
            "older_audit_id": batch[49].id if len(batch) > 50 else None,
            "is_older_audit_page": before is not None,
        },
    )
