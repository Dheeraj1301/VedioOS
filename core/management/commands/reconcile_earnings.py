import json

from django.core.management.base import BaseCommand, CommandError

from core.earnings_reconciliation import earnings_reconciliation_report


class Command(BaseCommand):
    help = "Check accepted-work earnings, coin-ledger and redemption consistency."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", dest="as_json")
        parser.add_argument("--report-only", action="store_true")

    def handle(self, *args, **options):
        report = earnings_reconciliation_report()
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
                "Earnings inventory: "
                f"wallets={report['wallet_count']}, acceptances={report['acceptance_count']}, "
                f"transactions={report['transaction_count']}, "
                f"redemptions={report['redemption_count']}."
            )
            self.stdout.write(f"Critical findings: {critical or 'none'}.")
            self.stdout.write(f"Operational warnings: {warnings or 'none'}.")
            self.stdout.write(f"Overall: {report['status'].upper()}")
        if report["status"] != "pass" and not options["report_only"]:
            raise CommandError(
                "Earnings reconciliation contains critical findings. Wallet, project and payout "
                "identifiers were omitted."
            )
