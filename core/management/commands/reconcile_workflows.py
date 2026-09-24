from django.core.management.base import BaseCommand, CommandError

from core.workflow_reconciliation import workflow_findings


class Command(BaseCommand):
    help = "Check cross-record workflow invariants without printing client or project identifiers."

    def handle(self, *args, **options):
        findings = workflow_findings()
        failures = {key: value for key, value in findings.items() if value}
        if failures:
            summary = ", ".join(f"{key}={value}" for key, value in failures.items())
            raise CommandError(
                f"Workflow reconciliation found inconsistent records: {summary}. "
                "Client, project, payment and file identifiers were omitted."
            )
        self.stdout.write(
            self.style.SUCCESS(
                "Workflow reconciliation passed: payment activation, assignment eligibility, ready-file "
                "metadata, version/revision linkage and delivery acceptance are consistent. No private "
                "identifiers were printed."
            )
        )
