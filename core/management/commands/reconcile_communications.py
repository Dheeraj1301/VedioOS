import json

from django.core.management.base import BaseCommand, CommandError

from core.communication_reconciliation import communication_reconciliation_report


class Command(BaseCommand):
    help = "Check project-message and private client-support consistency."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", dest="as_json")
        parser.add_argument("--report-only", action="store_true")

    def handle(self, *args, **options):
        report = communication_reconciliation_report()
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
                "Communication inventory: "
                f"project_messages={report['project_message_count']}, "
                f"support_requests={report['support_request_count']}, "
                f"support_messages={report['support_message_count']}."
            )
            self.stdout.write(f"Critical findings: {critical or 'none'}.")
            self.stdout.write(f"Operational warnings: {warnings or 'none'}.")
            self.stdout.write(f"Overall: {report['status'].upper()}")
        if report["status"] != "pass" and not options["report_only"]:
            raise CommandError(
                "Communication reconciliation contains critical findings. User, project, support "
                "and message identifiers and content were omitted."
            )
