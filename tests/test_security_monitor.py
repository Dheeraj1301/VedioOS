from unittest.mock import patch

from django.test import TestCase, override_settings

from core.models import User
from core.security_monitor import run_security_monitor
from operations.models import AuditLog, Notification


@override_settings(SECURITY_MONITOR_ENABLED=True, CRON_SECRET="synthetic-cron-secret")
class SecurityMonitorTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="security-admin@example.test",
            password="synthetic-password",
            name="Security Admin",
            role=User.Role.ADMIN,
        )

    @patch("core.security_monitor._check_cost", return_value=[{"code": "aws_cost", "level": "ok"}])
    @patch("core.security_monitor._check_guardduty", return_value=[{"code": "guardduty", "level": "ok"}])
    @patch("core.security_monitor._check_s3", return_value=[{"code": "s3_public_access", "level": "ok"}])
    def test_healthy_run_is_audited_without_notification(self, *_checks):
        result = run_security_monitor()
        self.assertEqual(result["status"], "healthy")
        self.assertTrue(AuditLog.objects.filter(action="security.monitor.completed").exists())
        self.assertFalse(Notification.objects.exists())

    @patch("core.security_monitor._check_cost", return_value=[])
    @patch(
        "core.security_monitor._check_guardduty",
        return_value=[{"code": "guardduty", "level": "critical", "finding_ids": ["finding-1"]}],
    )
    @patch("core.security_monitor._check_s3", return_value=[])
    def test_critical_finding_notifies_admin_once(self, *_checks):
        run_security_monitor()
        run_security_monitor()
        self.assertEqual(Notification.objects.filter(recipient=self.admin).count(), 1)
        notice = Notification.objects.get(recipient=self.admin)
        self.assertNotIn("finding-1", notice.event_key)
        self.assertNotIn("finding-1", notice.message)

    def test_cron_endpoint_fails_closed_without_valid_bearer_token(self):
        self.assertEqual(self.client.get("/internal/security-monitor/").status_code, 401)
        self.assertEqual(
            self.client.get(
                "/internal/security-monitor/", HTTP_AUTHORIZATION="Bearer wrong-secret"
            ).status_code,
            401,
        )

    @patch(
        "core.security_views.run_security_monitor",
        return_value={"status": "healthy", "critical_count": 0, "warning_count": 0},
    )
    def test_cron_endpoint_returns_only_summary(self, monitor):
        response = self.client.get(
            "/internal/security-monitor/",
            HTTP_AUTHORIZATION="Bearer synthetic-cron-secret",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "healthy", "critical_count": 0, "warning_count": 0},
        )
        monitor.assert_called_once_with()

    @override_settings(SECURITY_MONITOR_ENABLED=False)
    def test_cron_endpoint_reports_disabled_monitor(self):
        response = self.client.get(
            "/internal/security-monitor/",
            HTTP_AUTHORIZATION="Bearer synthetic-cron-secret",
        )
        self.assertEqual(response.status_code, 503)
