import json

from django.core.management.base import BaseCommand, CommandError

from core.commerce_reconciliation import commerce_reconciliation_report


class Command(BaseCommand):
    help = "Check quote, order, payment-event and paid-consultation consistency."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", dest="as_json")
        parser.add_argument("--report-only", action="store_true")

    def handle(self, *args, **options):
        report = commerce_reconciliation_report()
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
                "Commerce inventory: "
                f"orders={report['order_count']}, quotes={report['quote_count']}, "
                f"payments={report['payment_count']}, events={report['event_count']}, "
                f"calls={report['call_count']}."
            )
            self.stdout.write(f"Critical findings: {critical or 'none'}.")
            self.stdout.write(f"Operational warnings: {warnings or 'none'}.")
            self.stdout.write(f"Overall: {report['status'].upper()}")
        if report["status"] != "pass" and not options["report_only"]:
            raise CommandError(
                "Commerce reconciliation contains critical findings. Client and provider identifiers "
                "were omitted."
            )
