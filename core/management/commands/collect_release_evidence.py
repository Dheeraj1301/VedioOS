import json

from django.core.management.base import BaseCommand, CommandError

from core.release_evidence import collect_release_evidence


class Command(BaseCommand):
    help = "Collect secret-free database, workflow, storage and snapshot release evidence."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true")
        parser.add_argument("--report-only", action="store_true")
        parser.add_argument(
            "--active-storage",
            action="store_true",
            help="Also write, verify and remove a synthetic private-storage object.",
        )

    def handle(self, *args, **options):
        report = collect_release_evidence(active_storage=options["active_storage"])
        if options["json"]:
            self.stdout.write(json.dumps(report, sort_keys=True))
        else:
            self.stdout.write("VedioOS release evidence")
            for name, result in report["checks"].items():
                detail = ", ".join(
                    f"{key}={str(value).lower() if isinstance(value, bool) else value}"
                    for key, value in result.items()
                    if key not in {"status", "code"}
                )
                suffix = f" ({result['code']}{'; ' + detail if detail else ''})"
                self.stdout.write(f"- {name}: {result['status'].upper()}{suffix}")
            self.stdout.write(f"Overall: {report['status'].upper()}")
        if report["status"] != "pass" and not options["report_only"]:
            raise CommandError(
                "Release evidence contains failed required checks. Use the aggregate codes above; "
                "private identifiers and provider details were omitted."
            )
