import json

from django.core.management.base import BaseCommand, CommandError

from core.notification_reconciliation import notification_reconciliation_report


class Command(BaseCommand):
    help = "Check durable notification delivery state and eligibility without message content."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", dest="as_json")
        parser.add_argument("--report-only", action="store_true")

    def handle(self, *args, **options):
        report = notification_reconciliation_report()
        if options["as_json"]:
            self.stdout.write(json.dumps(report, sort_keys=True))
        else:
            states = ", ".join(f"{key}={value}" for key, value in report["states"].items())
            critical = ", ".join(
                f"{key}={value}" for key, value in report["critical"].items() if value
            )
            warnings = ", ".join(
                f"{key}={value}" for key, value in report["warnings"].items() if value
            )
            self.stdout.write(
                f"Notification outbox: notices={report['notice_count']}, "
                f"deliveries={report['delivery_count']}; {states}."
            )
            self.stdout.write(f"Critical findings: {critical or 'none'}.")
            self.stdout.write(f"Operational warnings: {warnings or 'none'}.")
            self.stdout.write(f"Overall: {report['status'].upper()}")
        if report["status"] != "pass" and not options["report_only"]:
            raise CommandError(
                "Notification outbox reconciliation contains critical findings. Recipient and "
                "message details were omitted."
            )
