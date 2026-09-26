import json

from django.core.management.base import BaseCommand, CommandError

from core.delivery_reconciliation import delivery_reconciliation_report


class Command(BaseCommand):
    help = "Check submitted versions, revisions and delivery acceptance consistency."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", dest="as_json")
        parser.add_argument("--report-only", action="store_true")

    def handle(self, *args, **options):
        report = delivery_reconciliation_report()
        if options["as_json"]:
            self.stdout.write(json.dumps(report, sort_keys=True))
        else:
            critical = ", ".join(
                f"{key}={value}" for key, value in report["critical"].items() if value
            )
            warnings = ", ".join(
                f"{key}={value}" for key, value in report["warnings"].items() if value
            )
            self.stdout.write(
                "Delivery inventory: "
                f"versions={report['version_count']}, revisions={report['revision_count']}, "
                f"acceptances={report['acceptance_count']}."
            )
            self.stdout.write(f"Critical findings: {critical or 'none'}.")
            self.stdout.write(f"Operational warnings: {warnings or 'none'}.")
            self.stdout.write(f"Overall: {report['status'].upper()}")
        if report["status"] != "pass" and not options["report_only"]:
            raise CommandError(
                "Delivery reconciliation contains critical findings. Project, version and file "
                "identifiers were omitted."
            )
