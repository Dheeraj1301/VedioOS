from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = "Check the active database and private-schema protections without exposing credentials."

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            self.stdout.write("Active database: local SQLite (not Supabase).")
            return
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(), current_schema(), current_user")
            database, schema, role = cursor.fetchone()
            self.stdout.write(f"Active database: PostgreSQL / {database} / schema {schema} / role {role}")
            cursor.execute(
                "SELECT count(*), count(*) FILTER (WHERE NOT rowsecurity) FROM pg_tables WHERE schemaname = %s",
                [schema],
            )
            total, unprotected = cursor.fetchone()
            self.stdout.write(f"Tables: {total}; without RLS: {unprotected}")
            cursor.execute(
                "SELECT has_schema_privilege('anon', %s, 'USAGE'), has_schema_privilege('authenticated', %s, 'USAGE')",
                [schema, schema],
            )
            anon, authenticated = cursor.fetchone()
            if schema != "vedioos" or not total or unprotected or anon or authenticated:
                raise CommandError("Private schema verification failed.")
            self.stdout.write(
                self.style.SUCCESS(
                    "Verified: application schema is private; browser API roles have no access."
                )
            )
