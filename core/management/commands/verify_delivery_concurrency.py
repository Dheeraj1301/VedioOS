"""Opt-in PostgreSQL races using exact synthetic fixtures; never flush shared data."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections, connection, connections, transaction

from core.delivery import transition
from core.models import (
    Client,
    DeliveryAcceptance,
    File,
    Order,
    Payment,
    Project,
    ProjectVersion,
    RevisionRequest,
    User,
)
from operations.models import AuditLog, Editor, EditorAssignment, EditorAvailability, Notification
from tests.assignment_fixtures import create_people
from tests.test_delivery import delivery_fixture, ready_output


class Command(BaseCommand):
    help = "Verify duplicate acceptance and competing review requests on PostgreSQL; remove exact synthetic fixtures."

    def handle(self, **options):
        if connection.vendor != "postgresql" or not settings.DEBUG:
            raise CommandError("Requires development PostgreSQL; never run with production payment settings.")
        with transaction.atomic():
            admin, buyer, editors = create_people()
            projects = [delivery_fixture(buyer, editors[0]) for _ in range(3)]
            versions = []
            for project in projects:
                file = ready_output(project, editors[0].user)
                transition(editors[0].user, project.pk, "start")
                transition(editors[0].user, project.pk, "submit", file_id=file.pk)
                versions.append(project.versions.get())
        ids = [p.pk for p in projects]
        users = [admin.pk, buyer.user_id] + [e.user_id for e in editors]

        def race(project, version, actions):
            barrier = Barrier(2)

            def worker(action):
                close_old_connections()
                try:
                    barrier.wait(timeout=15)
                    transition(
                        buyer.user, project.pk, action, version_id=version.pk, note="Synthetic revision"
                    )
                    return "ok"
                except ValidationError:
                    return "rejected"
                finally:
                    connections["default"].close()

            with ThreadPoolExecutor(max_workers=2) as pool:
                return list(pool.map(worker, actions))

        try:
            if race(projects[0], versions[0], ["accept", "accept"]) != ["ok", "ok"]:
                raise CommandError("Acceptance replay failed.")
            if DeliveryAcceptance.objects.filter(project=projects[0]).count() != 1:
                raise CommandError("Duplicate acceptance recorded.")
            result = race(projects[1], versions[1], ["accept", "revise"])
            if sorted(result) != ["ok", "rejected"]:
                raise CommandError("Competing review actions both succeeded.")
            if (
                race(projects[2], versions[2], ["revise", "revise"]) != ["ok", "ok"]
                or projects[2].revisions.count() != 1
            ):
                raise CommandError("Revision retry duplicated allowance usage.")
            self.stdout.write(
                "PASS: concurrent duplicate acceptance, accept-versus-revise, and duplicate revisions."
            )
        finally:
            with transaction.atomic():
                Notification.objects.filter(project_id__in=ids).delete()
                DeliveryAcceptance.objects.filter(project_id__in=ids).delete()
                RevisionRequest.objects.filter(project_id__in=ids).delete()
                ProjectVersion.objects.filter(project_id__in=ids).delete()
                File.objects.filter(project_id__in=ids).delete()
                EditorAssignment.objects.filter(project_id__in=ids).delete()
                AuditLog.objects.filter(actor_id__in=users).delete()
                Payment.objects.filter(order__project_id__in=ids).delete()
                Order.objects.filter(project_id__in=ids).delete()
                Project.objects.filter(pk__in=ids).delete()
                EditorAvailability.objects.filter(editor__in=editors).delete()
                Editor.objects.filter(pk__in=[e.pk for e in editors]).delete()
                Client.objects.filter(pk=buyer.pk).delete()
                User.objects.filter(pk__in=users).delete()
            self.stdout.write(
                "PASS: exact synthetic fixtures removed; existing orders and configuration unchanged."
            )
