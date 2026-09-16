"""Exercise real PostgreSQL locking using only temporary, precisely scoped fixtures."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections, connection, connections, transaction

from core.models import Client, Order, Payment, Project, User
from operations import assignments
from operations.models import (
    AssignmentPolicy,
    AssignmentQueue,
    AuditLog,
    Editor,
    EditorAssignment,
    EditorAvailability,
    ProjectComplexity,
)
from tests.assignment_fixtures import POLICY_VALUES, create_people, enable_test_policy, paid_project


class Command(BaseCommand):
    help = "Test concurrent allocation on PostgreSQL with temporary synthetic records, then remove only those records. Requires disabled live allocation."

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            raise CommandError("Real PostgreSQL is required to verify row locking.")
        policy = AssignmentPolicy.objects.get(pk=1)
        if policy.manual_enabled or policy.automatic_enabled:
            raise CommandError("Use an isolated database when live allocation is enabled.")
        original_lock = assignments.locked_policy

        def test_policy():
            row = original_lock()
            if row.manual_enabled or row.automatic_enabled:
                raise CommandError("Live allocation changed; stopping the test.")
            # Only this process sees these temporary values. Shared configuration stays disabled.
            for key, value in POLICY_VALUES.items():
                setattr(row, key, value)
            return row

        marker = uuid.uuid4().hex
        with transaction.atomic():
            admin, client, editors = create_people(prefix=marker)
            projects = [
                paid_project(client, title=f"TEST concurrency {marker} {index}") for index in range(3)
            ]
        project_ids = [project.id for project in projects]
        editor_ids = [editor.id for editor in editors]
        user_ids = [admin.id, client.user_id, *[editor.user_id for editor in editors]]
        try:
            with patch.object(assignments, "locked_policy", test_policy):
                for project in projects:
                    assignments.classify(
                        admin, project.id, "beginner", "Temporary concurrency verification", 0
                    )

                def race(jobs):
                    barrier = Barrier(2)

                    def worker(job):
                        close_old_connections()
                        try:
                            barrier.wait(timeout=10)
                            assignment = assignments.manual_assign(
                                admin, job[0], job[1], "Temporary concurrency verification"
                            )
                            return str(assignment.id)
                        except ValidationError:
                            return "rejected"
                        finally:
                            connections["default"].close()

                    with ThreadPoolExecutor(max_workers=2) as executor:
                        return list(executor.map(worker, jobs))

                results = race([(projects[0].id, editors[0].id), (projects[0].id, editors[1].id)])
                if (
                    results.count("rejected") != 1
                    or EditorAssignment.objects.filter(project=projects[0], ended_at__isnull=True).count()
                    != 1
                ):
                    raise CommandError("Concurrent duplicate assignment check failed.")
                self.stdout.write("PASS: concurrent admins cannot double-assign one project.")
                results = race([(projects[1].id, editors[2].id), (projects[2].id, editors[2].id)])
                if results.count("rejected") != 1 or assignments.open_workload(editors[2]) != 1:
                    raise CommandError("Concurrent capacity check failed.")
                self.stdout.write("PASS: concurrent projects cannot exceed editor capacity.")
        finally:
            # Exact fixture IDs only. Never flush or truncate the shared database.
            with transaction.atomic():
                EditorAssignment.objects.filter(project_id__in=project_ids).delete()
                AssignmentQueue.objects.filter(project_id__in=project_ids).delete()
                ProjectComplexity.objects.filter(project_id__in=project_ids).delete()
                AuditLog.objects.filter(actor_id=admin.id).delete()
                Payment.objects.filter(order__project_id__in=project_ids).delete()
                Order.objects.filter(project_id__in=project_ids).delete()
                Project.objects.filter(id__in=project_ids).delete()
                EditorAvailability.objects.filter(editor_id__in=editor_ids).delete()
                Editor.objects.filter(id__in=editor_ids).delete()
                Client.objects.filter(id=client.id).delete()
                User.objects.filter(id__in=user_ids).delete()
        self.stdout.write(
            "PASS: all temporary fixtures removed; live policy and rotation positions unchanged."
        )
        with transaction.atomic():
            enable_test_policy()
            temporary_admin, temporary_client, _ = create_people()
            project = paid_project(temporary_client, title="TEST rolled-back round-robin verification")
            assignments.classify(temporary_admin, project.id, "beginner", "Temporary verification", 0)
            first = assignments.assign_next(project.id, temporary_admin)
            second = assignments.assign_next(project.id, temporary_admin)
            if not first or first.id != second.id:
                raise CommandError("PostgreSQL round-robin idempotency failed.")
            transaction.set_rollback(True)
        self.stdout.write(
            "PASS: PostgreSQL automatic allocation and retry; all smoke-test changes rolled back."
        )
