from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import Client, Project, User
from operations.models import Notification, NotificationDelivery
from operations.notifications import dispatch_due, release_held


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    NOTIFICATION_EMAIL_ENABLED=True,
    NOTIFICATION_DELIVERY_MAX_ATTEMPTS=3,
)
class NotificationDeliveryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.client_user = User.objects.create_user(
            "notice-client@example.test", "Synthetic-72!Leaf", name="Client"
        )
        cls.project = Project.objects.create(
            client=Client.objects.create(user=cls.client_user), title="Notice project"
        )
        cls.editor_user = User.objects.create_user(
            "notice-editor@example.test", "Synthetic-72!Leaf", name="Editor", role="editor"
        )

    def test_success_is_claimed_and_sent_once(self):
        notice = Notification.objects.create(
            recipient=self.client_user,
            project=self.project,
            event_key="delivery-success",
            message="Your project has an update.",
        )
        self.assertEqual(notice.delivery.state, "pending")
        processed = dispatch_due()
        self.assertEqual(len(processed), 1)
        delivery = NotificationDelivery.objects.get(notification=notice)
        self.assertEqual(delivery.state, "sent")
        self.assertEqual(delivery.attempts, 1)
        self.assertIsNotNone(delivery.sent_at)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(dispatch_due(), [])
        self.assertEqual(len(mail.outbox), 1)

    def test_failure_retries_with_safe_error_code(self):
        notice = Notification.objects.create(
            recipient=self.client_user,
            event_key="delivery-retry",
            message="Account update.",
        )
        with patch("operations.notifications.EmailMessage.send", side_effect=TimeoutError("secret")):
            processed = dispatch_due()
        self.assertEqual(len(processed), 1)
        delivery = NotificationDelivery.objects.get(notification=notice)
        self.assertEqual(delivery.state, "failed")
        self.assertEqual(delivery.last_error_code, "TimeoutError")
        self.assertNotIn("secret", delivery.last_error_code)
        delivery.next_attempt_at = timezone.now()
        delivery.save(update_fields=["next_attempt_at", "updated_at"])
        dispatch_due()
        delivery.refresh_from_db()
        self.assertEqual(delivery.state, "sent")
        self.assertEqual(delivery.attempts, 2)

    def test_project_access_is_rechecked_before_external_delivery(self):
        notice = Notification.objects.create(
            recipient=self.editor_user,
            project=self.project,
            event_key="former-editor-delivery",
            message="Private project update.",
        )
        processed = dispatch_due()
        self.assertEqual(len(processed), 1)
        delivery = NotificationDelivery.objects.get(notification=notice)
        self.assertEqual(delivery.state, "cancelled")
        self.assertEqual(delivery.last_error_code, "recipient_ineligible")
        self.assertEqual(len(mail.outbox), 0)


@override_settings(NOTIFICATION_EMAIL_ENABLED=False)
class HeldNotificationDeliveryTests(TestCase):
    def test_external_delivery_is_held_by_default(self):
        user = User.objects.create_user(
            "held-notice@example.test", "Synthetic-72!Leaf", name="Held"
        )
        notice = Notification.objects.create(
            recipient=user, event_key="held-delivery", message="Held update."
        )
        self.assertEqual(notice.delivery.state, "held")
        self.assertEqual(dispatch_due(), [])
        self.assertEqual(release_held(), 0)
