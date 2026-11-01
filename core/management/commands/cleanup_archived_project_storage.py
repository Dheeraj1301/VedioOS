from django.core.management.base import BaseCommand

from core.models import ProjectStorageCleanup
from core.project_storage import process_cleanup_job


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
        for job in jobs:
            if process_cleanup_job(job.pk):
                completed += 1
            else:
                self.stderr.write(f"Storage cleanup will retry project job {job.pk}.")
        self.stdout.write(
            self.style.SUCCESS(f"Storage cleanup processed={len(jobs)}, completed={completed}.")
        )
