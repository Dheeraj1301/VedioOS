import json
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from core.release_readiness import MANUAL_GATES, release_findings


class ReleaseReadinessTests(TestCase):
    def secure_config(self):
        return {
            "debug": False,
            "secret_key": "s" * 64,
            "allowed_hosts": ["app.example.test"],
            "csrf_trusted_origins": ["https://app.example.test"],
            "database_engine": "django.db.backends.postgresql",
            "database_options": {"sslmode": "verify-full", "sslrootcert": "/secure/ca.crt"},
            "storage_endpoint": "https://storage.example.test",
            "storage_bucket": "private-media",
            "email_backend": "example.EmailBackend",
            "default_from_email": "VedioOS <no-reply@example.test>",
            "payment_mode": "disabled",
            "payout_mode": "disabled",
            "notification_email_enabled": False,
            "session_cookie_secure": True,
            "csrf_cookie_secure": True,
            "ssl_redirect": True,
            "hsts_seconds": 31536000,
        }

    def disabled_policies(self):
        return {
            "quotes_enabled": False,
            "automatic_assignment": False,
            "earnings_enabled": False,
            "redemptions_enabled": False,
            "uploads_enabled": True,
        }

    def test_secure_disabled_scope_has_warnings_but_no_configuration_blockers(self):
        findings = release_findings(self.secure_config(), self.disabled_policies())
        self.assertFalse([item for item in findings if item["severity"] == "blocker"])
        self.assertIn("payments_disabled", {item["code"] for item in findings})
        self.assertTrue(MANUAL_GATES)

    def test_insecure_or_inconsistent_configuration_fails_closed(self):
        config = self.secure_config()
        config.update(
            {
                "debug": True,
                "secret_key": "short-secret",
                "allowed_hosts": ["*"],
                "csrf_trusted_origins": [],
                "database_engine": "django.db.backends.sqlite3",
                "database_options": {},
                "storage_endpoint": "http://127.0.0.1:9000",
                "email_backend": "django.core.mail.backends.console.EmailBackend",
                "default_from_email": "no-reply@localhost",
                "payment_mode": "sandbox",
                "payout_mode": "sandbox",
                "notification_email_enabled": True,
                "session_cookie_secure": False,
                "csrf_cookie_secure": False,
                "ssl_redirect": False,
                "hsts_seconds": 0,
            }
        )
        policies = self.disabled_policies()
        policies.update({"uploads_enabled": False, "quotes_enabled": True, "redemptions_enabled": True})
        codes = {
            item["code"]
            for item in release_findings(config, policies)
            if item["severity"] == "blocker"
        }
        self.assertTrue(
            {
                "debug_enabled",
                "weak_secret_key",
                "allowed_hosts",
                "csrf_origins",
                "session_cookie",
                "csrf_cookie",
                "ssl_redirect",
                "hsts",
                "database_backend",
                "database_tls",
                "storage_tls",
                "email_backend",
                "sender_domain",
                "payment_sandbox",
                "payout_sandbox",
                "uploads_disabled",
            }.issubset(codes)
        )

    def test_json_report_does_not_print_secret_values(self):
        output = StringIO()
        call_command("check_release", report_only=True, as_json=True, stdout=output)
        payload = json.loads(output.getvalue())
        self.assertIn("findings", payload)
        self.assertIn("manual_gates", payload)
        self.assertNotIn("SECRET_KEY", output.getvalue())
        self.assertNotIn("DATABASE_URL", output.getvalue())
