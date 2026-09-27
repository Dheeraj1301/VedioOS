"""Confirm that a preview is bound to the selected shared Supabase database."""

import os
from urllib.parse import urlparse

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from core.models import Client, Project, User


class Command(BaseCommand):
    help = "Verify shared Supabase binding without printing credentials or user data."

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            raise CommandError("Preview is not using PostgreSQL.")

        expected_ref = settings.SUPABASE_PROJECT_REF
        configured_url = os.environ.get("DATABASE_URL", "")
        parsed = urlparse(configured_url)
        identity = f"{parsed.username or ''}@{parsed.hostname or ''}"
        if not expected_ref or expected_ref not in identity:
            raise CommandError("Database connection does not match SUPABASE_PROJECT_REF.")

        with connection.cursor() as cursor:
            cursor.execute("select current_schema()")
            current_schema = cursor.fetchone()[0]
        if current_schema != "vedioos":
            raise CommandError(f"Expected private schema vedioos; got {current_schema!r}.")

        pending = MigrationExecutor(connection).migration_plan(
            MigrationExecutor(connection).loader.graph.leaf_nodes()
        )
        if pending:
            raise CommandError(f"Shared database has {len(pending)} pending migration(s).")

        self.stdout.write(self.style.SUCCESS("PASS: selected Supabase project is connected"))
        self.stdout.write(self.style.SUCCESS("PASS: current schema is vedioos"))
        self.stdout.write(self.style.SUCCESS("PASS: database migrations are current"))
        self.stdout.write(
            f"Aggregate records: users={User.objects.count()}, "
            f"clients={Client.objects.count()}, projects={Project.objects.count()}"
        )
