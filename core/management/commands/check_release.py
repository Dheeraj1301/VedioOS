import json

from django.core.management.base import BaseCommand, CommandError

from core.release_readiness import (
    MANUAL_GATES,
    current_policy_state,
    current_release_config,
    release_findings,
)


class Command(BaseCommand):
    help = "Audit production runtime configuration without printing secret values."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", dest="as_json")
        parser.add_argument(
            "--report-only",
            action="store_true",
            help="Return success while reporting blockers; useful during development.",
        )

    def handle(self, *args, **options):
        findings = release_findings(current_release_config(), current_policy_state())
        blockers = [item for item in findings if item["severity"] == "blocker"]
        if options["as_json"]:
            self.stdout.write(
                json.dumps({"findings": findings, "manual_gates": MANUAL_GATES}, sort_keys=True)
            )
        else:
            for item in findings:
                self.stdout.write(
                    f"{item['severity'].upper()} [{item['code']}]: {item['message']}"
                )
            self.stdout.write("Manual release gates:")
            for gate in MANUAL_GATES:
                self.stdout.write(f"- {gate}")
            self.stdout.write(
                f"Result: {len(blockers)} configuration blocker(s), "
                f"{len(findings) - len(blockers)} warning(s)."
            )
        if blockers and not options["report_only"]:
            raise CommandError("Production configuration is not ready.")
