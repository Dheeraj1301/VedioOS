import json

from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError

from core.database_security import database_security_report


class Command(BaseCommand):
    help = "Audit PostgreSQL runtime privileges, private-schema grants and recovery inventory."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", dest="as_json")
        parser.add_argument("--report-only", action="store_true")

    def handle(self, *args, **options):
        try:
            report = database_security_report()
        except DatabaseError:
            raise CommandError(
                "Database security inspection failed; credentials and provider details were omitted."
            ) from None
        if options["as_json"]:
            self.stdout.write(json.dumps(report, sort_keys=True))
        else:
            facts = report["facts"]
            if facts.get("vendor") == "postgresql":
                self.stdout.write(
                    f"PostgreSQL security inventory: {facts['table_count']} tables, "
                    f"{len(facts['extensions'])} extensions, "
                    f"{facts['enabled_event_triggers']} enabled event trigger(s)."
                )
                self.stdout.write(
                    "Runtime role elevation flags: "
                    f"{facts['role_elevated_flags']}; finite connection limit: "
                    f"{facts['role_connection_limit']}."
                )
                self.stdout.write(
                    "Public/browser grants: "
                    f"schema={facts['public_schema_privileges'] + facts['browser_schema_privileges']}, "
                    f"tables={facts['browser_table_grants']}, "
                    f"sequences={facts['browser_sequence_grants']}, "
                    f"routines={facts['browser_routine_grants']}, "
                    f"defaults={facts['browser_default_grants']}."
                )
                extension_inventory = ", ".join(
                    f"{item['name']} {item['version']} ({item['schema']})"
                    for item in facts["extensions"]
                )
                self.stdout.write(f"Recovery extension inventory: {extension_inventory}.")
            if report["findings"]:
                self.stdout.write("Findings: " + ", ".join(report["findings"]))
            self.stdout.write(f"Overall: {report['status'].upper()}")
        if report["status"] != "pass" and not options["report_only"]:
            raise CommandError(
                "Database security audit failed. Output omits database credentials and private rows."
            )
