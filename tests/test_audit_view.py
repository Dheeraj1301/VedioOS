from django.test import TestCase

from core.models import Client, User
from operations.models import AuditLog


class AuditTimelineTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            "audit-admin@example.test", "synthetic", name="Manager", role="admin"
        )
        self.client_user = User.objects.create_user("audit-client@example.test", "synthetic", name="Client")
        Client.objects.create(user=self.client_user)
        self.editor = User.objects.create_user(
            "audit-editor@example.test", "synthetic", name="Editor", role="editor"
        )

    def test_admin_only_cursor_history_omits_private_details(self):
        for number in range(55):
            AuditLog.objects.create(
                actor=self.admin if number % 2 else None,
                action="synthetic.checked",
                target_id=f"record-{number:02d}",
                detail={"signed_url": "https://private.example.test/secret"},
            )
        self.assertEqual(self.client.get("/admin/audit/").status_code, 302)
        for user in [self.client_user, self.editor]:
            self.client.force_login(user)
            self.assertEqual(self.client.get("/admin/audit/").status_code, 403)
        self.client.force_login(self.admin)
        newest = self.client.get("/admin/audit/")
        self.assertEqual(len(newest.context["events"]), 50)
        self.assertContains(newest, "record-54")
        self.assertNotContains(newest, "record-00")
        self.assertNotContains(newest, "private.example.test")
        cursor = newest.context["older_audit_id"]
        AuditLog.objects.create(action="synthetic.new", target_id="newer", detail={})
        older = self.client.get("/admin/audit/", {"before": cursor})
        self.assertEqual(len(older.context["events"]), 5)
        self.assertContains(older, "record-00")
        self.assertNotContains(older, "newer")
        self.assertEqual(self.client.get("/admin/audit/?before=bad").status_code, 404)
        self.assertEqual(self.client.get("/admin/audit/?before=99999999999999999999").status_code, 404)

    def test_empty_audit_view(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get("/admin/audit/"), "No audit events yet")
