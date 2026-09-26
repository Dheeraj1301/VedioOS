import json

from django.core.management.base import BaseCommand, CommandError

from core.assignment_reconciliation import assignment_reconciliation_report


class Command(BaseCommand):
    help = "Check assignment policy, queues, capacity and round-robin consistency."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", dest="as_json")
        parser.add_argument("--report-only", action="store_true")

    def handle(self, *args, **options):
        report = assignment_reconciliation_report()
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
                "Assignment inventory: "
                f"complexities={report['complexity_count']}, queues={report['queue_count']}, "
                f"assignments={report['assignment_count']}, rotations={report['rotation_count']}."
            )
            self.stdout.write(f"Critical findings: {critical or 'none'}.")
            self.stdout.write(f"Operational warnings: {warnings or 'none'}.")
            self.stdout.write(f"Overall: {report['status'].upper()}")
        if report["status"] != "pass" and not options["report_only"]:
            raise CommandError(
                "Assignment reconciliation contains critical findings. Project, editor and queue "
                "identifiers were omitted."
            )
