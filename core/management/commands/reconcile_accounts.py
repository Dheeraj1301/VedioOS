import json

from django.core.management.base import BaseCommand, CommandError

from core.account_reconciliation import account_reconciliation_report


class Command(BaseCommand):
    help = "Check identity, role-profile and active-session consistency without personal data."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", dest="as_json")
        parser.add_argument("--report-only", action="store_true")

    def handle(self, *args, **options):
        report = account_reconciliation_report()
        if options["as_json"]:
            self.stdout.write(json.dumps(report, sort_keys=True))
        else:
            self.stdout.write(
                "Account inventory: "
                f"users={report['user_count']}, clients={report['client_count']}, "
                f"editors={report['editor_count']}, admins={report['admin_count']}, "
                f"authenticated sessions={report['authenticated_sessions']}."
            )
            critical = ", ".join(
                f"{key}={value}" for key, value in report["critical"].items() if value
            )
            warnings = ", ".join(
                f"{key}={value}" for key, value in report["warnings"].items() if value
            )
            self.stdout.write(f"Critical findings: {critical or 'none'}.")
            self.stdout.write(f"Lifecycle warnings: {warnings or 'none'}.")
            self.stdout.write(f"Overall: {report['status'].upper()}")
        if report["status"] != "pass" and not options["report_only"]:
            raise CommandError(
                "Account reconciliation contains critical findings. Personal identifiers were omitted."
            )
