"""Retry-safe in-app alerts for projects with an already-recorded deadline."""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import Project
from core.views import audit
from operations.calls import notify, notify_admins
from operations.models import EditorAssignment


class Command(BaseCommand):
    help = "Notify admins and current editors about paid projects past a recorded deadline. Safe to rerun."

    def handle(self, *args, **options):
        count = 0
        projects = Project.objects.filter(
            order__payment_status="confirmed", expected_delivery_at__lt=timezone.now()
        ).exclude(status__in=["completed", "cancelled"])
        for candidate in projects.iterator():
            with transaction.atomic():
                project = Project.objects.select_for_update().select_related("order").get(pk=candidate.pk)
                if (
                    project.order.payment_status != "confirmed"
                    or project.status in ["completed", "cancelled"]
                    or not project.expected_delivery_at
                    or project.expected_delivery_at >= timezone.now()
                ):
                    continue
                key = f"deadline:{project.pk}:{project.expected_delivery_at.isoformat()}"
                created = notify_admins(
                    project, key, "A paid project is past its recorded delivery deadline."
                )
                assignment = (
                    EditorAssignment.objects.filter(project=project, ended_at__isnull=True)
                    .select_related("editor__user")
                    .first()
                )
                if assignment:
                    editor_created = notify(
                        assignment.editor.user,
                        project,
                        f"{key}:editor:{assignment.pk}",
                        "Your assigned project is past its recorded delivery deadline.",
                    )
                    created = created or editor_created
                if created:
                    audit(
                        None,
                        "deadline.overdue_alerted",
                        project.pk,
                        {"deadline": project.expected_delivery_at.isoformat()},
                    )
                count += 1
        self.stdout.write(f"Checked {count} overdue paid projects; existing alerts were not duplicated.")
