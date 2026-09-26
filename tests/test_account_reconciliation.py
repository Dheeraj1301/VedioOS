import json
from io import StringIO
from unittest.mock import patch

from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from core.account_reconciliation import account_reconciliation_report
from core.models import Client, User
from operations.models import Admin, Editor, EditorAvailability, EditorCoins

PASSWORD = "Synthetic-Account-72!Leaf"


class AccountReconciliationTests(TestCase):
    def create_consistent_accounts(self):
        client_user = User.objects.create_user(
            "account-client@example.test", PASSWORD, name="Client"
        )
        Client.objects.create(user=client_user)
        editor_user = User.objects.create_user(
            "account-editor@example.test", PASSWORD, name="Editor", role="editor"
        )
        editor = Editor.objects.create(
            user=editor_user,
            phone="",
            experience="",
            tools="",
            portfolio="",
            previous_work="",
            expertise="",
        )
        EditorAvailability.objects.create(editor=editor)
        EditorCoins.objects.create(editor=editor)
        admin_user = User.objects.create_user(
            "account-admin@example.test", PASSWORD, name="Admin", role="admin"
        )
        Admin.objects.create(user=admin_user)

    def test_consistent_role_profiles_pass(self):
        self.create_consistent_accounts()
        report = account_reconciliation_report()
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["critical_count"], 0)
        self.assertEqual(report["user_count"], 3)

    def test_missing_profile_and_inactive_session_are_aggregated(self):
        user = User.objects.create_user(
            "missing-profile@example.test",
            PASSWORD,
            name="Missing",
            is_active=False,
        )
        session = self.client.session
        session["_auth_user_id"] = str(user.pk)
        session["_auth_user_backend"] = "django.contrib.auth.backends.ModelBackend"
        session["_auth_user_hash"] = user.get_session_auth_hash()
        session.save()
        report = account_reconciliation_report()
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["critical"]["client_role_missing_profile"], 1)
        self.assertEqual(report["critical"]["sessions_for_inactive_users"], 1)
        self.assertNotIn(user.email, json.dumps(report))

    def test_expired_sessions_are_not_counted(self):
        self.create_consistent_accounts()
        Session.objects.create(
            session_key="expired-session",
            session_data="invalid",
            expire_date=timezone.now() - timezone.timedelta(minutes=1),
        )
        self.assertEqual(account_reconciliation_report()["authenticated_sessions"], 0)


class AccountReconciliationCommandTests(TestCase):
    def test_command_failure_is_secret_free_and_fail_closed(self):
        report = {
            "status": "fail",
            "code": "account_reconciliation_failed",
            "user_count": 1,
            "client_count": 0,
            "editor_count": 0,
            "admin_count": 0,
            "authenticated_sessions": 0,
            "critical": {"client_role_missing_profile": 1},
            "warnings": {},
            "critical_count": 1,
            "warning_count": 0,
        }
        with patch(
            "core.management.commands.reconcile_accounts.account_reconciliation_report",
            return_value=report,
        ):
            with self.assertRaisesMessage(CommandError, "critical findings"):
                call_command("reconcile_accounts", stdout=StringIO())
