import hashlib
import json
import re
from io import StringIO
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.test import Client as Browser
from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import Client, File, Order, Project, UploadPolicy, User
from operations.models import (
    Admin,
    AuditLog,
    Editor,
    EditorAssignment,
    EditorAvailability,
    EditorCoins,
    EditorProficiency,
    RoundRobinState,
)

PASSWORD = "Synthetic-Creator-72!Leaf"


class FoundationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("client@example.test", PASSWORD, name="Client One")
        cls.other = User.objects.create_user("other@example.test", PASSWORD, name="Client Two")
        cls.profile = Client.objects.create(user=cls.owner)
        Client.objects.create(user=cls.other)
        cls.admin = User.objects.create_user("admin@example.test", PASSWORD, name="Admin", role="admin")
        Admin.objects.create(user=cls.admin)
        cls.editor_user = User.objects.create_user(
            "editor@example.test", PASSWORD, name="Editor", role="editor"
        )
        cls.editor = Editor.objects.create(
            user=cls.editor_user,
            phone="1234567890",
            experience="Editing",
            tools="Resolve",
            portfolio="https://example.com",
            previous_work="Reels",
            expertise="Color",
        )
        EditorAvailability.objects.create(editor=cls.editor)
        EditorCoins.objects.create(editor=cls.editor)
        cls.project = Project.objects.create(client=cls.profile, title="Synthetic edit")
        Order.objects.create(project=cls.project)
        UploadPolicy.objects.create(max_bytes=1024, allowed_types={".mp4": ["video/mp4"]})

    def auth(self, user):
        browser = Browser()
        browser.force_login(user)
        return browser

    def post_json(self, browser, url, data):
        return browser.post(url, data=json.dumps(data), content_type="application/json")

    def upload_data(self):
        return {
            "filename": "clip.mp4",
            "size_bytes": 12,
            "content_type": "video/mp4",
            "sha256": hashlib.sha256(b"hello world!").hexdigest(),
            "category": "source",
        }

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_client_registration_verification_login_logout(self):
        browser = Browser()
        response = browser.post(
            "/register/",
            {"name": "New Client", "email": "NEW@example.test", "password1": PASSWORD, "password2": PASSWORD},
        )
        self.assertRedirects(response, "/verify-email/")
        user = User.objects.get(email="new@example.test")
        self.assertEqual(user.role, "client")
        self.assertTrue(user.check_password(PASSWORD))
        self.assertFalse(user.is_active)
        self.assertIsNone(user.email_verified_at)
        self.assertTrue(Client.objects.filter(user=user).exists())
        self.assertEqual(len(mail.outbox), 1)
        blocked_login = browser.post(
            "/login/", {"username": "NEW@example.test", "password": PASSWORD}
        )
        self.assertEqual(blocked_login.status_code, 200)
        self.assertFalse(browser.session.get("_auth_user_id"))
        mail.outbox.clear()
        self.assertRedirects(
            browser.post("/verify-email/resend/", {"email": "NEW@example.test"}),
            "/verify-email/",
        )
        self.assertEqual(len(mail.outbox), 1)
        verification_url = re.search(r"https?://[^\s]+/verify-email/[^\s]+/", mail.outbox[0].body).group()
        self.assertRedirects(browser.get(verification_url), "/client/")
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertIsNotNone(user.email_verified_at)
        session_key = browser.session.session_key
        self.assertEqual(browser.post("/logout/").status_code, 302)
        from django.contrib.sessions.models import Session

        self.assertFalse(Session.objects.filter(session_key=session_key).exists())
        self.assertEqual(browser.get("/api/areas/client/").status_code, 401)
        self.assertRedirects(
            browser.post("/login/", {"username": "NEW@example.test", "password": PASSWORD}),
            "/dashboard/",
            fetch_redirect_response=False,
        )
        self.assertEqual(browser.get("/client/").status_code, 200)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_verification_resend_is_generic_and_invalid_tokens_are_rejected(self):
        browser = Browser()
        self.assertRedirects(
            browser.post("/verify-email/resend/", {"email": "missing@example.test"}),
            "/verify-email/",
        )
        self.assertEqual(len(mail.outbox), 0)
        response = browser.get("/verify-email/not-a-valid-token/")
        self.assertEqual(response.status_code, 400)
        self.assertNotContains(response, "not-a-valid-token", status_code=400)

    def editor_data(self):
        return {
            "name": "New Editor",
            "email": "neweditor@example.test",
            "password1": PASSWORD,
            "password2": PASSWORD,
            "phone": "9876543210",
            "experience": "Two years",
            "tools": "Premiere",
            "portfolio": "https://example.com/portfolio",
            "previous_work": "Reel sample",
            "expertise": "Color grading",
            "availability": "available",
            "other_information": "",
        }

    def test_admin_issued_editor_id_and_login(self):
        browser = Browser()
        self.assertRedirects(browser.get("/register/editor/"), "/login/")
        with patch("operations.management.commands.create_editor.getpass", return_value=PASSWORD):
            call_command(
                "create_editor",
                email="neweditor@example.test",
                name="New Editor",
                editor_id="VED-TEST0001",
                stdout=StringIO(),
            )
        user = User.objects.get(email="neweditor@example.test")
        self.assertEqual(user.role, "editor")
        self.assertFalse(user.editor_profile.approved)
        self.assertIsNone(user.editor_profile.proficiency_id)
        self.assertEqual(user.editor_profile.login_id, "VED-TEST0001")
        self.assertEqual(user.editor_profile.availability.status, "offline")
        self.assertRedirects(
            browser.post("/login/", {"username": "ved-test0001", "password": PASSWORD}),
            "/dashboard/",
            fetch_redirect_response=False,
        )
        self.assertContains(browser.get("/editor/"), "awaiting approval")

    def test_client_password_requires_owner_approved_composition(self):
        invalid = [
            "lowercase8!",
            "UPPERCASE8!",
            "NoNumber!",
            "NoSpecial8",
            "Aa1!aaa",
        ]
        for index, password in enumerate(invalid):
            response = Browser().post(
                "/register/",
                {
                    "name": "Password Test",
                    "email": f"password-{index}@example.test",
                    "password1": password,
                    "password2": password,
                },
            )
            with self.subTest(password=password):
                self.assertEqual(response.status_code, 200)
                self.assertFalse(User.objects.filter(email=f"password-{index}@example.test").exists())

    def test_music_preferences_remove_duplicate_and_offer_both(self):
        choices = dict(Project._meta.get_field("song_choice").choices)
        self.assertNotIn("known", choices)
        self.assertEqual(
            choices["both"],
            "I will provide a song and would also like editor suggestions",
        )

    def test_admin_provisioning_and_login(self):
        with patch("core.management.commands.create_admin.getpass", return_value=PASSWORD):
            call_command("create_admin", email="manager@example.test", name="Manager", stdout=StringIO())
        user = User.objects.get(email="manager@example.test")
        self.assertTrue(Admin.objects.filter(user=user).exists())
        browser = Browser()
        self.assertEqual(
            browser.post("/login/", {"username": user.email, "password": PASSWORD}).status_code, 302
        )
        self.assertEqual(browser.get("/admin/").status_code, 200)

    def test_role_matrix_on_pages_and_apis(self):
        for user in [self.owner, self.editor_user, self.admin]:
            browser = self.auth(user)
            for role in ["client", "editor", "admin"]:
                status = 200 if user.role == role else 403
                with self.subTest(user=user.role, area=role):
                    self.assertEqual(browser.get(f"/{role}/").status_code, status)
                    self.assertEqual(browser.get(f"/api/areas/{role}/").status_code, status)
        self.assertEqual(Browser().get("/admin/").status_code, 302)

    def test_all_navigation_pages_load(self):
        from core.context import NAV

        for user in [self.owner, self.editor_user, self.admin]:
            browser = self.auth(user)
            for label, url in NAV[user.role]:
                with self.subTest(label=label):
                    self.assertEqual(browser.get(url).status_code, 200)

    def test_cross_project_and_unassigned_editor_denied(self):
        for user in [self.other, self.editor_user]:
            browser = self.auth(user)
            self.assertEqual(browser.get(f"/api/projects/{self.project.id}/").status_code, 404)
            self.assertEqual(browser.get(f"/{user.role}/projects/{self.project.id}/").status_code, 404)

    def test_assignment_and_reassignment_access(self):
        self.editor.approved = True
        self.editor.proficiency_id = "beginner"
        self.editor.approved_by = self.admin
        self.editor.save()
        self.project.payment_completed_at = timezone.now()
        self.project.status = "editor_assigned"
        self.project.save()
        assignment = EditorAssignment.objects.create(
            project=self.project, editor=self.editor, assigned_by=self.admin
        )
        browser = self.auth(self.editor_user)
        self.assertEqual(browser.get(f"/editor/projects/{self.project.id}/").status_code, 200)
        assignment.ended_at = timezone.now()
        assignment.save()
        self.assertEqual(browser.get(f"/api/projects/{self.project.id}/").status_code, 404)

    def test_no_public_privilege_escalation(self):
        browser = Browser()
        data = self.editor_data()
        for field in ["role", "approved", "proficiency", "is_staff", "is_superuser"]:
            self.assertEqual(browser.post("/register/editor/", {**data, field: "admin"}).status_code, 302)
            self.assertEqual(browser.post("/register/", {**data, field: "admin"}).status_code, 403)
        self.assertFalse(User.objects.filter(email=data["email"]).exists())
        self.assertEqual(
            self.auth(self.editor_user)
            .post(f"/admin/editors/{self.editor.id}/approve/", {"proficiency": "advanced"})
            .status_code,
            403,
        )
        self.assertEqual(
            self.auth(self.editor_user)
            .post("/editor/availability/", {"status": "available", "approved": "true"})
            .status_code,
            403,
        )

    def test_admin_approval_audited(self):
        browser = self.auth(self.admin)
        self.assertEqual(
            browser.post(
                f"/admin/editors/{self.editor.id}/approve/", {"proficiency": "intermediate"}
            ).status_code,
            302,
        )
        self.editor.refresh_from_db()
        self.assertTrue(self.editor.approved)
        self.assertEqual(self.editor.proficiency_id, "intermediate")
        self.assertTrue(
            AuditLog.objects.filter(action="editor.proficiency_approved", actor=self.admin).exists()
        )

    def test_project_draft_cannot_be_marked_paid_by_browser(self):
        response = self.auth(self.owner).post(
            "/client/new-order/",
            {
                "title": "New draft",
                "song_choice": "suggest",
                "status": "completed",
                "payment_completed_at": "2026-01-01",
            },
        )
        self.assertEqual(response.status_code, 302)
        project = Project.objects.get(title="New draft")
        self.assertEqual(project.status, "payment_pending")
        self.assertIsNone(project.payment_completed_at)
        self.assertEqual(project.order.payment_status, "pending")

    def test_private_file_access_denied(self):
        file = File.objects.create(
            project=self.project,
            uploader=self.owner,
            filename="clip.mp4",
            object_key="private/key",
            size_bytes=12,
            sha256="0" * 64,
            content_type="video/mp4",
            category="source",
            state="ready",
            storage_version="v1",
            expires_at=timezone.now(),
        )
        self.assertEqual(Browser().post(f"/api/files/{file.id}/download/").status_code, 401)
        for user in [self.other, self.editor_user]:
            browser = self.auth(user)
            self.assertEqual(browser.post(f"/api/files/{file.id}/download/").status_code, 404)
            self.assertEqual(browser.post(f"/api/files/{file.id}/complete/").status_code, 404)
        self.assertNotContains(
            self.auth(self.owner).get(f"/client/projects/{self.project.id}/"), "private/key"
        )

    def test_upload_validation_and_owner_check(self):
        browser = self.auth(self.owner)
        url = f"/api/projects/{self.project.id}/uploads/"
        for changes in [
            {"size_bytes": 1025},
            {"filename": "../clip.mp4"},
            {"filename": "clip.exe"},
            {"sha256": "bad"},
            {"size_bytes": -1},
            {"content_type": "text/html"},
        ]:
            self.assertEqual(self.post_json(browser, url, {**self.upload_data(), **changes}).status_code, 400)
        self.assertEqual(
            self.post_json(browser, url, {**self.upload_data(), "category": "final"}).status_code, 403
        )
        self.assertEqual(self.post_json(self.auth(self.other), url, self.upload_data()).status_code, 404)

    def test_csrf_protects_mutations(self):
        browser = Browser(enforce_csrf_checks=True)
        browser.force_login(self.owner)
        self.assertEqual(browser.post("/client/new-order/", {"title": "Unsafe"}).status_code, 403)
        self.assertEqual(browser.post("/logout/").status_code, 403)

    def test_case_insensitive_identity_and_constraints(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user("CLIENT@example.test", PASSWORD)
        self.assertEqual(EditorProficiency.objects.count(), 3)
        self.assertEqual(RoundRobinState.objects.count(), 3)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.editor.approved = True
            self.editor.save()

    def test_required_tables_exist(self):
        expected = {
            "users",
            "clients",
            "projects",
            "orders",
            "plans",
            "custom_services",
            "payments",
            "files",
            "project_versions",
            "revision_requests",
            "influencer_packages",
            "subscriptions",
            "editors",
            "admins",
            "editor_proficiency",
            "editor_availability",
            "project_complexity",
            "editor_assignments",
            "assignment_queue",
            "round_robin_state",
            "call_requests",
            "notifications",
            "editor_coins",
            "coin_transactions",
            "redemption_requests",
            "audit_logs",
        }
        self.assertTrue(expected <= set(connection.introspection.table_names()))

    def test_private_pages_not_cached(self):
        response = self.auth(self.owner).get("/client/")
        self.assertEqual(response["Cache-Control"], "no-store, private")
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")

    def test_auth_rate_limit(self):
        browser = Browser()
        from core.models import AuthAttempt

        AuthAttempt.objects.create(
            key=hashlib.sha256(b"127.0.0.1").hexdigest(), failures=30, window_started=timezone.now()
        )
        self.assertEqual(
            browser.post("/login/", {"username": self.owner.email, "password": PASSWORD}).status_code, 429
        )
