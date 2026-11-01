from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from core.models import Project
from core.permissions import role_required
from core.project_storage import DELETABLE_STATUSES, delete_project_files
from core.views import audit

from .storage_costs import storage_cost_report


@require_GET
@role_required("admin")
def storage_costs(request):
    return render(request, "operations/storage_costs.html", {"title": "Storage costs", **storage_cost_report()})


@require_POST
@role_required("admin")
def delete_project_storage(request, project_id):
    project = get_object_or_404(Project, pk=project_id)
    if request.POST.get("confirm") != "yes":
        messages.error(request, "Tick the confirmation box to delete this project's files.")
        return redirect("storage_costs")
    if project.archived_at is None and project.status not in DELETABLE_STATUSES:
        messages.error(request, "Only completed or cancelled projects can be deleted.")
        return redirect("storage_costs")
    cleaned = delete_project_files(project.pk)
    audit(request.user, "project.storage_deleted", project.pk, {"storage_cleared": cleaned})
    if cleaned:
        messages.success(request, f"{project.title} was deleted and its files were removed from storage.")
    else:
        messages.warning(
            request,
            f"{project.title} was deleted. Storage could not be reached, so file removal will retry automatically.",
        )
    return redirect("storage_costs")
