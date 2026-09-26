import json
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import User
from core.notification_reconciliation import notification_reconciliation_report
from operations.models import Notification, NotificationDelivery


@override_settings(NOTIFICATION_EMAIL_ENABLED=False, NOTIFICATION_DELIVERY_MAX_ATTEMPTS=3)
class NotificationReconciliationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "outbox-reconcile@example.test", "Synthetic-72!Leaf", name="Recipient"
        )

    def test_held_delivery_is_consistent_when_provider_is_disabled(self):
        Notification.objects.create(recipient=self.user, event_key="held", message="Update")
        report = notification_reconciliation_report()
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["states"]["held"], 1)
        self.assertEqual(report["critical_count"], 0)

    def test_invalid_sent_metadata_and_unsafe_reference_fail(self):
        notice = Notification.objects.create(recipient=self.user, event_key="sent", message="Update")
        NotificationDelivery.objects.filter(notification=notice).update(
            state="sent",
            attempts=1,
            sent_at=None,
            provider_reference="https://private.example.test/token",
        )
        report = notification_reconciliation_report()
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["critical"]["sent_state_metadata"], 1)
        self.assertEqual(report["critical"]["unsafe_provider_references"], 1)
        self.assertNotIn("private.example.test", json.dumps(report))

    def test_inactive_recipient_cannot_remain_pending(self):
        notice = Notification.objects.create(recipient=self.user, event_key="pending", message="Update")
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        NotificationDelivery.objects.filter(notification=notice).update(
            state="pending", next_attempt_at=timezone.now()
        )
        report = notification_reconciliation_report()
        self.assertEqual(report["critical"]["ineligible_queued_deliveries"], 1)


class NotificationReconciliationCommandTests(TestCase):
    def test_command_fails_closed_with_aggregate_output(self):
        report = {
            "status": "fail",
            "code": "notification_outbox_failed",
            "notice_count": 1,
            "delivery_count": 0,
            "states": {"held": 0},
            "critical": {"notices_missing_delivery": 1},
            "warnings": {},
            "critical_count": 1,
            "warning_count": 0,
        }
        output = StringIO()
        with patch(
            "core.management.commands.reconcile_notification_outbox.notification_reconciliation_report",
            return_value=report,
        ):
            with self.assertRaisesMessage(CommandError, "critical findings"):
                call_command("reconcile_notification_outbox", stdout=output)
        self.assertNotIn("recipient", output.getvalue().lower())
