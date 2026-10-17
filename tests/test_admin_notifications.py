from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from operations.models import Notification, NotificationCampaign
from tests.assignment_fixtures import create_people


class AdminNotificationTests(TestCase):
    def setUp(self):
        self.admin, self.client_profile, self.editors = create_people()

    def test_admin_create_publish_detail_read_and_unpublish(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            "/admin/notifications/new/",
            {"title": "Service update", "body": "A detailed update for clients.", "audience": "clients"},
        )
        self.assertRedirects(response, "/admin/notifications/")
        campaign = NotificationCampaign.objects.get(title="Service update")
        self.assertEqual(campaign.status, "draft")
        self.client.post(f"/admin/notifications/{campaign.pk}/action/", {"action": "publish"})
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, "published")
        notice = Notification.objects.get(campaign=campaign, recipient=self.client_profile.user)
        self.assertFalse(Notification.objects.filter(campaign=campaign, recipient=self.editors[0].user).exists())

        self.client.force_login(self.client_profile.user)
        dashboard = self.client.get("/client/")
        self.assertContains(dashboard, "Service update")
        self.assertNotContains(dashboard, ">Notifications<span", html=False)
        detail = self.client.get(f"/notifications/{notice.pk}/")
        self.assertContains(detail, "A detailed update for clients.")
        notice.refresh_from_db()
        self.assertIsNotNone(notice.read_at)

        self.client.force_login(self.admin)
        self.client.post(f"/admin/notifications/{campaign.pk}/action/", {"action": "unpublish"})
        self.client.force_login(self.client_profile.user)
        self.assertNotContains(self.client.get("/client/"), "Service update")
        self.assertEqual(self.client.get(f"/notifications/{notice.pk}/").status_code, 404)

    def test_non_admin_cannot_manage_and_mark_all_is_recipient_scoped(self):
        campaign = NotificationCampaign.objects.create(
            title="Everyone", body="Shared", audience="all", created_by=self.admin, status="published"
        )
        own = Notification.objects.create(
            recipient=self.client_profile.user, campaign=campaign, event_key="own-campaign", message="Shared"
        )
        other = Notification.objects.create(
            recipient=self.editors[0].user, campaign=campaign, event_key="other-campaign", message="Shared"
        )
        self.client.force_login(self.client_profile.user)
        self.assertEqual(self.client.get("/admin/notifications/").status_code, 403)
        self.client.post("/notifications/mark-all-read/")
        own.refresh_from_db()
        other.refresh_from_db()
        self.assertIsNotNone(own.read_at)
        self.assertIsNone(other.read_at)

    def test_poster_validation_and_private_access(self):
        png = b"\x89PNG\r\n\x1a\n" + b"synthetic-image"
        self.client.force_login(self.admin)
        self.client.post(
            "/admin/notifications/new/",
            {
                "title": "Poster notice",
                "body": "Has a cover",
                "audience": "clients",
                "poster_upload": SimpleUploadedFile("cover.png", png, content_type="image/png"),
            },
        )
        campaign = NotificationCampaign.objects.get(title="Poster notice")
        self.assertEqual(bytes(campaign.poster), png)
        self.assertEqual(self.client.get(f"/notifications/posters/{campaign.pk}/").status_code, 200)
        self.client.logout()
        self.assertEqual(self.client.get(f"/notifications/posters/{campaign.pk}/").status_code, 302)

        self.client.force_login(self.admin)
        bad = SimpleUploadedFile("bad.png", BytesIO(b"not an image").read(), content_type="image/png")
        response = self.client.post(
            "/admin/notifications/new/",
            {"title": "Bad", "body": "Bad poster", "audience": "all", "poster_upload": bad},
        )
        self.assertContains(response, "not a valid supported image")
        self.assertFalse(NotificationCampaign.objects.filter(title="Bad").exists())
