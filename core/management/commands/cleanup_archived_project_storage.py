from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import File, ProjectStorageCleanup
from core.storage import delete_private_object_versions


class Command(BaseCommand):
    help = "Permanently remove private objects queued by archived client projects."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=25)

    def handle(self, *args, **options):
        limit = max(1, min(options["limit"], 250))
        jobs = list(
            ProjectStorageCleanup.objects.filter(
                state__in=[ProjectStorageCleanup.State.PENDING, ProjectStorageCleanup.State.RETRY]
            )
            .order_by("created_at")[:limit]
        )
        completed = 0
        for candidate in jobs:
            with transaction.atomic():
                job = ProjectStorageCleanup.objects.select_for_update().get(pk=candidate.pk)
                if job.state not in {
                    ProjectStorageCleanup.State.PENDING,
                    ProjectStorageCleanup.State.RETRY,
                }:
                    continue
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
                self.stderr.write(f"Storage cleanup will retry project job {job.pk}.")
                continue
            now = timezone.now()
            with transaction.atomic():
                File.objects.filter(project_id=job.project_id).update(state="removed", updated_at=now)
                ProjectStorageCleanup.objects.filter(pk=job.pk).update(
                    state=ProjectStorageCleanup.State.COMPLETED,
                    object_count=len(files),
                    completed_at=now,
                    updated_at=now,
                )
            completed += 1
        self.stdout.write(
            self.style.SUCCESS(f"Storage cleanup processed={len(jobs)}, completed={completed}.")
        )
