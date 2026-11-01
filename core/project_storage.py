"""Remove an archived project's private objects, every stored version included."""

from django.db import transaction
from django.utils import timezone

from .models import File, Project, ProjectStorageCleanup
from .storage import delete_private_object_versions

DELETABLE_STATUSES = {Project.Status.COMPLETED, Project.Status.CANCELLED}


def process_cleanup_job(job_pk):
    """Run one queued cleanup; return True when its objects are gone, False to retry later."""
    with transaction.atomic():
        job = ProjectStorageCleanup.objects.select_for_update().get(pk=job_pk)
        if job.state not in {ProjectStorageCleanup.State.PENDING, ProjectStorageCleanup.State.RETRY}:
            return job.state == ProjectStorageCleanup.State.COMPLETED
        job.state = ProjectStorageCleanup.State.PROCESSING
        job.attempts += 1
        job.last_attempt_at = timezone.now()
        job.save(update_fields=["state", "attempts", "last_attempt_at", "updated_at"])
    try:
        files = list(File.objects.filter(project_id=job.project_id).only("pk", "object_key"))
        for file in files:
            delete_private_object_versions(file.object_key)
    except Exception:
        ProjectStorageCleanup.objects.filter(pk=job.pk).update(
            state=ProjectStorageCleanup.State.RETRY,
            updated_at=timezone.now(),
        )
        return False
    now = timezone.now()
    with transaction.atomic():
        File.objects.filter(project_id=job.project_id).update(state="removed", updated_at=now)
        ProjectStorageCleanup.objects.filter(pk=job.pk).update(
            state=ProjectStorageCleanup.State.COMPLETED,
            object_count=len(files),
            completed_at=now,
            updated_at=now,
        )
    return True


def delete_project_files(project_id):
    """Archive a finished project and remove its stored files; return True when storage is clean."""
    with transaction.atomic():
        project = Project.objects.select_for_update().get(pk=project_id)
        if project.archived_at is None:
            if project.status not in DELETABLE_STATUSES:
                raise ValueError("Only completed or cancelled projects can be deleted.")
            project.archived_at = timezone.now()
            project.save(update_fields=["archived_at", "updated_at"])
        ProjectStorageCleanup.objects.get_or_create(project=project)
    return process_cleanup_job(project.pk)
