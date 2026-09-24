import json
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase


class ReleaseEvidenceCommandTests(SimpleTestCase):
    def report(self, status="pass"):
        return {
            "status": status,
            "checks": {
                "database": {"status": status, "code": "ready"},
                "snapshot": {"status": "skipped", "code": "no_local_snapshot"},
            },
        }

    def test_json_report_is_machine_readable_and_secret_free(self):
        output = StringIO()
        with patch(
            "core.management.commands.collect_release_evidence.collect_release_evidence",
            return_value=self.report(),
        ) as collect:
            call_command("collect_release_evidence", "--json", stdout=output)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["status"], "pass")
        self.assertNotIn("DATABASE_URL", output.getvalue())
        self.assertNotIn("signed_url", output.getvalue())
        collect.assert_called_once_with(active_storage=False)

    def test_failure_stops_release_workflow(self):
        with patch(
            "core.management.commands.collect_release_evidence.collect_release_evidence",
            return_value=self.report("fail"),
        ):
            with self.assertRaisesMessage(CommandError, "failed required checks"):
                call_command("collect_release_evidence", stdout=StringIO())

    def test_report_only_records_failure_and_active_storage_selection(self):
        output = StringIO()
        with patch(
            "core.management.commands.collect_release_evidence.collect_release_evidence",
            return_value=self.report("fail"),
        ) as collect:
            call_command(
                "collect_release_evidence",
                "--report-only",
                "--active-storage",
                stdout=output,
            )
        self.assertIn("Overall: FAIL", output.getvalue())
        collect.assert_called_once_with(active_storage=True)
