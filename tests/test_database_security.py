import json
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from core.database_security import database_security_findings


def secure_facts(**changes):
    facts = {
        "vendor": "postgresql",
        "schema": "vedioos",
        "role_elevated_flags": 0,
        "role_connection_limit": 8,
        "schema_owned_by_runtime_role": True,
        "public_schema_privileges": 0,
        "browser_roles_present": 2,
        "browser_schema_privileges": 0,
        "table_count": 46,
        "tables_without_rls": 0,
        "tables_not_owned_by_runtime_role": 0,
        "browser_table_grants": 0,
        "browser_sequence_grants": 0,
        "browser_routine_grants": 0,
        "browser_default_grants": 0,
        "extensions": [{"name": "plpgsql", "version": "1.0", "schema": "pg_catalog"}],
        "enabled_event_triggers": 1,
    }
    facts.update(changes)
    return facts


class DatabaseSecurityFindingTests(SimpleTestCase):
    def test_expected_private_database_has_no_findings(self):
        self.assertEqual(database_security_findings(secure_facts()), [])

    def test_elevated_role_and_browser_grants_fail_closed(self):
        findings = database_security_findings(
            secure_facts(role_elevated_flags=1, browser_table_grants=3)
        )
        self.assertEqual(findings, ["runtime_role_elevated", "browser_table_grants"])

    def test_non_postgresql_database_is_not_release_evidence(self):
        self.assertEqual(
            database_security_findings({"vendor": "sqlite"}),
            ["postgresql_required"],
        )


class DatabaseSecurityCommandTests(SimpleTestCase):
    def test_json_output_is_secret_free(self):
        output = StringIO()
        report = {"status": "pass", "code": "protected", "findings": [], "facts": secure_facts()}
        with patch(
            "core.management.commands.audit_database_security.database_security_report",
            return_value=report,
        ):
            call_command("audit_database_security", "--json", stdout=output)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["status"], "pass")
        self.assertNotIn("DATABASE_URL", output.getvalue())
        self.assertNotIn("password", output.getvalue().lower())

    def test_failed_audit_stops_release_workflow(self):
        report = {
            "status": "fail",
            "code": "database_security_failed",
            "findings": ["runtime_role_elevated"],
            "facts": {"vendor": "sqlite"},
        }
        with patch(
            "core.management.commands.audit_database_security.database_security_report",
            return_value=report,
        ):
            with self.assertRaisesMessage(CommandError, "security audit failed"):
                call_command("audit_database_security", stdout=StringIO())
