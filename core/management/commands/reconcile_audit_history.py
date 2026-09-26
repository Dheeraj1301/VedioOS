import json

from django.core.management.base import BaseCommand, CommandError

from core.audit_reconciliation import audit_reconciliation_report


class Command(BaseCommand):
    help = "Check sensitive-record audit coverage and detail redaction without private payloads."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", dest="as_json")
        parser.add_argument("--report-only", action="store_true")

    def handle(self, *args, **options):
        report = audit_reconciliation_report()
        if options["as_json"]:
            self.stdout.write(json.dumps(report, sort_keys=True))
        else:
            critical = ", ".join(
                f"{key}={value}" for key, value in report["critical"].items() if value
            )
            warnings = ", ".join(
                f"{key}={value}" for key, value in report["warnings"].items() if value
            )
            self.stdout.write(f"Audit history inventory: events={report['event_count']}.")
            self.stdout.write(f"Critical findings: {critical or 'none'}.")
            self.stdout.write(f"Legacy warnings: {warnings or 'none'}.")
            self.stdout.write(f"Overall: {report['status'].upper()}")
        if report["status"] != "pass" and not options["report_only"]:
            raise CommandError(
                "Audit history reconciliation contains critical findings. Event payloads and private "
                "identifiers were omitted."
            )
