import hashlib
import json
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from botocore.exceptions import ClientError
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.test import Client as Browser
from django.test import TestCase
from django.utils import timezone
from django.utils.html import strip_tags

from core.models import (
    Client,
    EmailVerificationChallenge,
    File,
    Order,
    Plan,
    PolicyAcceptance,
    Project,
    UploadPolicy,
    User,
)
from operations.models import (
    Admin,
    AuditLog,
    Editor,
    EditorAssignment,
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

    def test_registration_shows_one_concise_password_instruction(self):
        response = Browser().get("/register/")
        self.assertContains(response, "Make room for your next idea.")
        self.assertContains(response, "Password confirmation")
        self.assertContains(response, 'name="password2"', html=False)
        self.assertContains(response, 'type="submit">Create account')
        self.assertContains(
            response,
            "Use at least 8 characters with an uppercase letter, lowercase letter, "
            "number, and special character.",
            count=1,
        )
        self.assertNotContains(response, "commonly used password")
        self.assertNotContains(response, "entirely numeric")
        self.assertNotContains(response, "too similar to your other personal information")
        for removed_copy in (
            "Your creative space",
            "◈",
            "Original quality.",
            "Private by design.",
            "Human, always.",
            "Create your client account. Your footage stays private.",
            "How it works",
            "Services",
            "Enter the same password as before, for verification.",
        ):
            self.assertNotContains(response, removed_copy)

    def test_public_auth_header_shows_only_the_alternate_action(self):
        login = Browser().get("/login/")
        self.assertContains(login, ">Start creating</a>", count=1)
        self.assertNotContains(login, '>Log in</a><a class="button small"')

        register = Browser().get("/register/")
        self.assertContains(register, ">Log in</a>", count=2)
        self.assertNotContains(register, ">Start creating <")

    def test_client_overview_discards_queued_flash_messages(self):
        browser = Browser()
        with patch("core.views.send_verification_email", side_effect=RuntimeError):
            self.assertRedirects(
                browser.post(
                    "/register/",
                    {
                        "name": "Queued Message Client",
                        "email": "queued-message@example.test",
                        "password1": PASSWORD,
                        "password2": PASSWORD,
                        "accept_terms": "yes",
                        "policy_version": "0",
                    },
                ),
                "/verify-email/",
            )
        browser.force_login(self.owner)
        response = browser.get("/client/")
        self.assertEqual(response.status_code, 200)
        notice = "Your account was saved, but the verification email could not be sent."
        self.assertNotContains(response, notice)
        self.assertNotContains(response, "Good references make great edits")
        self.assertNotContains(browser.get("/client/"), notice)

    def test_client_registration_verification_login_logout(self):
        browser = Browser()
        with patch("core.views.send_verification_email") as send_code:
            response = browser.post(
                "/register/",
                {
                    "name": "New Client",
                    "email": "NEW@example.test",
                    "password1": PASSWORD,
                    "password2": PASSWORD,
                    "accept_terms": "yes",
                    "policy_version": "0",
                },
            )
        self.assertRedirects(response, "/verify-email/")
        user = User.objects.get(email="new@example.test")
        self.assertEqual(user.role, "client")
        self.assertTrue(user.check_password(PASSWORD))
        self.assertFalse(user.is_active)
        self.assertIsNone(user.email_verified_at)
        self.assertTrue(Client.objects.filter(user=user).exists())
        acceptance = PolicyAcceptance.objects.get(user=user, context="registration")
        self.assertEqual(acceptance.policy_version, 0)
        self.assertIsNotNone(acceptance.accepted_at)
        self.assertIn("mandatory statutory rights", acceptance.policy_snapshot["no_refund_policy"])
        self.assertIn("support", acceptance.policy_snapshot["support_statement"].lower())
        send_code.assert_called_once_with("new@example.test")
        blocked_login = browser.post(
            "/login/", {"username": "NEW@example.test", "password": PASSWORD}
        )
        self.assertEqual(blocked_login.status_code, 200)
        self.assertFalse(browser.session.get("_auth_user_id"))
        with patch("core.views.check_verification_code", return_value="verified") as verify_code:
            self.assertRedirects(
                browser.post(
                    "/verify-email/code/",
                    {"email": "NEW@example.test", "code": "123456"},
                ),
                "/verify-email/success/",
            )
        verify_code.assert_called_once_with("new@example.test", "123456")
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

    def test_verification_resend_is_generic_and_invalid_tokens_are_rejected(self):
        browser = Browser()
        with patch("core.views.send_verification_email") as send_code:
            self.assertRedirects(
                browser.post("/verify-email/resend/", {"email": "missing@example.test"}),
                "/verify-email/",
            )
        send_code.assert_not_called()
        response = browser.get("/verify-email/not-a-valid-token/")
        self.assertEqual(response.status_code, 404)

    def test_resend_and_code_verification_are_delegated_to_supabase(self):
        user = User.objects.create_user(
            "otp@example.test", PASSWORD, name="OTP Client", is_active=False
        )
        Client.objects.create(user=user)
        with patch("core.views.send_verification_email") as send_code:
            self.assertRedirects(
                Browser().post("/verify-email/resend/", {"email": user.email}),
                "/verify-email/",
            )
        send_code.assert_called_once_with(user.email)
        browser = Browser()
        with patch(
            "core.views.check_verification_code", side_effect=["invalid", "verified"]
        ) as verify_code:
            self.assertRedirects(
                browser.post(
                    "/verify-email/code/", {"email": user.email, "code": "111111"}
                ),
                "/verify-email/",
            )
            self.assertFalse(browser.session.get("_auth_user_id"))
            self.assertRedirects(
                browser.post(
                    "/verify-email/code/", {"email": user.email, "code": "222222"}
                ),
                "/verify-email/success/",
            )
        self.assertEqual(verify_code.call_count, 2)
        self.assertFalse(EmailVerificationChallenge.objects.filter(user=user).exists())

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
        self.assertEqual(user.editor_profile.assignments.count(), 0)
        self.assertRedirects(
            browser.post("/login/", {"username": "ved-test0001", "password": PASSWORD}),
            "/dashboard/",
            fetch_redirect_response=False,
        )
        self.assertContains(browser.get("/editor/"), "awaiting approval")

    def test_editor_sign_in_entry_flow_and_role_separation(self):
        entry = Browser().get("/")
        self.assertContains(entry, 'href="/editor/signin/">Editor Sign In')

        browser = Browser()
        response = browser.get("/editor/signin/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Use your administrator-issued editor ID or editor email.")
        self.assertContains(response, '<label for="id_username">Email</label>', html=True)
        for removed_copy in (
            "or editor ID",
            "Welcome back",
            "Your creative space",
            "◈",
            "Original quality.",
            "Original quality preserved",
            "Your files stay private",
            "HUMAN EDITED",
            "Private by design.",
            "Human, always.",
            "How it works",
            "Services",
            "Human craft. Every frame.",
        ):
            self.assertNotContains(response, removed_copy)
        self.assertContains(response, 'type="submit">Editor Sign In')

        client_sign_in = browser.get("/login/")
        self.assertContains(client_sign_in, "Back to your next great edit.")
        self.assertContains(client_sign_in, '<label for="id_username">Email</label>', html=True)
        self.assertContains(client_sign_in, "Welcome back")
        for removed_copy in (
            "or editor ID",
            "Your creative space",
            "◈",
            "Original quality.",
            "Original quality preserved",
            "Your files stay private",
            "HUMAN EDITED",
            "Private by design.",
            "Human, always.",
            "How it works",
            "Services",
            "Human craft. Every frame.",
        ):
            self.assertNotContains(client_sign_in, removed_copy)

        invalid = browser.post(
            "/editor/signin/",
            {"username": self.editor.login_id, "password": "not-the-password"},
        )
        self.assertEqual(invalid.status_code, 200)
        self.assertContains(invalid, "Please enter a correct email and password")
        self.assertFalse(browser.session.get("_auth_user_id"))

        self.assertRedirects(
            browser.post(
                "/editor/signin/",
                {"username": self.editor.login_id.lower(), "password": PASSWORD},
            ),
            "/editor/",
        )
        self.assertEqual(browser.session.get("_auth_user_id"), str(self.editor_user.pk))

        for user in [self.owner, self.admin]:
            role_browser = Browser()
            denied = role_browser.post(
                "/editor/signin/",
                {"username": user.email, "password": PASSWORD},
            )
            with self.subTest(role=user.role):
                self.assertEqual(denied.status_code, 200)
                self.assertContains(denied, "This sign-in is for editor accounts")
                self.assertFalse(role_browser.session.get("_auth_user_id"))

        regular_client = Browser()
        self.assertRedirects(
            regular_client.post(
                "/login/", {"username": self.owner.email, "password": PASSWORD}
            ),
            "/dashboard/",
            fetch_redirect_response=False,
        )
        self.assertRedirects(regular_client.get("/dashboard/"), "/client/")

        regular_admin = Browser()
        self.assertRedirects(
            regular_admin.post(
                "/login/", {"username": self.admin.email, "password": PASSWORD}
            ),
            "/dashboard/",
            fetch_redirect_response=False,
        )
        self.assertRedirects(regular_admin.get("/dashboard/"), "/admin/")

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

    def test_client_registration_requires_current_policy_acceptance(self):
        data = {
            "name": "Consent Test",
            "email": "consent@example.test",
            "password1": PASSWORD,
            "password2": PASSWORD,
        }
        missing = Browser().post("/register/", data)
        self.assertEqual(missing.status_code, 200)
        self.assertContains(missing, "Review and accept the Terms and Conditions")
        self.assertFalse(User.objects.filter(email=data["email"]).exists())

        stale = Browser().post(
            "/register/",
            {**data, "accept_terms": "yes", "policy_version": "99"},
        )
        self.assertEqual(stale.status_code, 200)
        self.assertContains(stale, "Terms and Conditions changed")
        self.assertFalse(User.objects.filter(email=data["email"]).exists())

    def test_music_preferences_remove_duplicate_and_offer_both(self):
        choices = dict(Project._meta.get_field("song_choice").choices)
        self.assertNotIn("known", choices)
        self.assertEqual(
            choices["both"],
            "I will provide my own song and would also like editor's suggestion",
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

    def test_admin_sidebar_hides_calls_audit_and_notifications_only(self):
        from core.context import NAV

        self.assertEqual(
            NAV["admin"],
            [
                ("Overview", "/admin/"),
                ("Orders", "/admin/orders/"),
                ("Payments", "/admin/payments/"),
                ("Editors", "/admin/editors/"),
                ("Clients", "/admin/clients/"),
                ("Assignments", "/admin/assignments/"),
                ("Plans / Pricing", "/admin/pricing/"),
                ("Landing page", "/admin/landing-page/"),
                ("Feature controls", "/admin/features/"),
                ("Payouts", "/admin/payouts/"),
                ("Support", "/admin/support/"),
                ("Analytics", "/admin/analytics/"),
            ],
        )
        browser = self.auth(self.admin)
        dashboard = browser.get("/admin/")
        for hidden_label in ["Calls", "Audit", "Notifications"]:
            self.assertNotContains(dashboard, f">{hidden_label}<span", html=False)
        self.assertEqual(browser.get("/admin/calls/").status_code, 200)
        self.assertEqual(browser.get("/admin/audit/").status_code, 200)
        self.assertEqual(browser.get("/admin/notifications/").status_code, 200)

    def test_admin_editor_search_and_sort(self):
        john_user = User.objects.create_user(
            "johnny@example.test", PASSWORD, name="Johnny Rivera", role="editor"
        )
        john = Editor.objects.create(
            user=john_user,
            login_id="VED-ZZZ0000001",
            phone="1111111111",
            experience="Editing",
            tools="Resolve",
            portfolio="https://example.com/john",
            previous_work="Reels",
            expertise="Color",
        )
        priya_user = User.objects.create_user(
            "priya@example.test", PASSWORD, name="Priya Shah", role="editor"
        )
        Editor.objects.create(
            user=priya_user,
            login_id="VED-AAA0000001",
            phone="2222222222",
            experience="Editing",
            tools="Premiere",
            portfolio="https://example.com/priya",
            previous_work="Shorts",
            expertise="Motion",
        )
        Editor.objects.filter(pk=john.pk).update(created_at=timezone.now() - timedelta(days=2))
        browser = self.auth(self.admin)

        for query in ["jOh", "JOHNNY@EXAMPLE", "zzz000"]:
            with self.subTest(query=query):
                response = browser.get("/admin/editors/", {"q": query})
                self.assertContains(response, "Johnny Rivera")
                self.assertNotContains(response, "Priya Shah")

        empty = browser.get("/admin/editors/", {"q": "no-such-editor"})
        self.assertContains(empty, "No editors found.")

        combined = browser.get("/admin/editors/", {"q": "example.test", "sort": "id_asc"})
        content = combined.content.decode()
        self.assertLess(content.index("Priya Shah"), content.index("Johnny Rivera"))
        self.assertContains(combined, 'value="id_asc" checked')
        self.assertContains(combined, "Non-default sort active")

        newest = browser.get("/admin/editors/").content.decode()
        self.assertLess(newest.index("Priya Shah"), newest.index("Johnny Rivera"))

    def test_admin_editor_search_controls_render(self):
        response = self.auth(self.admin).get("/admin/editors/")
        self.assertContains(response, "Search name, email, or editor ID")
        self.assertContains(response, '<button class="button small" type="submit">Search</button>')
        for label in [
            "Newest to Oldest",
            "Oldest to Newest",
            "Alphabetical (A → Z)",
            "Alphabetical (Z → A)",
            "Editor ID (Ascending)",
            "Editor ID (Descending)",
            "Clear / Reset",
        ]:
            self.assertContains(response, label)

    def test_admin_editor_list_is_minimal_and_detail_retains_profile(self):
        browser = self.auth(self.admin)
        response = browser.get("/admin/editors/", {"q": self.editor.login_id})
        content = response.content.decode()
        editor_cards = content.split('<ul class="data-list">', 1)[1].split("</ul>", 1)[0]
        visible_text = strip_tags(editor_cards)
        self.assertContains(response, f'href="/admin/editors/{self.editor.id}/"')
        self.assertContains(response, "Editor")
        self.assertContains(response, "Awaiting review")
        self.assertContains(response, "Admin proficiency decision")
        self.assertContains(response, "Select level")
        self.assertContains(response, "Approve level")
        for hidden_value in [
            self.editor.login_id,
            self.editor_user.email,
            self.editor.phone,
            self.editor.experience,
            self.editor.tools,
            self.editor.expertise,
            self.editor.previous_work,
            "Active projects",
            "Availability",
            "View portfolio",
            "Manage capacity & eligibility",
        ]:
            self.assertNotIn(hidden_value, visible_text)

        detail = browser.get(f"/admin/editors/{self.editor.id}/")
        self.assertEqual(detail.status_code, 200)
        for detail_value in [
            self.editor.login_id,
            self.editor_user.email,
            self.editor.phone,
            self.editor.experience,
            self.editor.tools,
            self.editor.expertise,
            self.editor.previous_work,
            "Active projects",
            "Availability",
            "View portfolio",
        ]:
            self.assertContains(detail, detail_value)
        self.assertNotContains(detail, "Manage capacity &amp; eligibility")

        self.assertEqual(self.auth(self.owner).get(f"/admin/editors/{self.editor.id}/").status_code, 403)

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
        assignment = EditorAssignment.objects.create(
            project=self.project, editor=self.editor, assigned_by=self.admin
        )
        browser = self.auth(self.editor_user)
        self.assertEqual(browser.get(f"/editor/projects/{self.project.id}/").status_code, 404)

        self.project.payment_completed_at = timezone.now()
        self.project.status = "editor_assigned"
        self.project.save()
        Order.objects.filter(project=self.project).update(payment_status="confirmed")
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
            self.auth(self.editor_user).post("/editor/availability/", {"status": "available"}).status_code,
            200,
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
                "order_choice": "custom",
                "reel_duration": "30_50",
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

    def test_custom_order_fields_and_font_inspiration_are_server_validated(self):
        browser = self.auth(self.owner)
        missing_direction = browser.post(
            "/client/new-order/",
            {
                "title": "Wording reel",
                "order_choice": "custom",
                "reel_duration": "20_30",
                "wants_wording": "on",
                "song_choice": "suggest",
            },
        )
        self.assertEqual(missing_direction.status_code, 200)
        self.assertContains(missing_direction, "Choose how the editor should handle wording")
        response = browser.post(
            "/client/new-order/",
            {
                "title": "Wording reel",
                "order_choice": "custom",
                "colour_grading": "on",
                "quality_enhancement": "on",
                "overlays": "on",
                "beat_sync": "on",
                "reel_duration": "60_plus",
                "wants_wording": "on",
                "wording_direction": "font_inspiration",
                "song_choice": "both",
            },
        )
        self.assertEqual(response.status_code, 302)
        project = Project.objects.get(title="Wording reel")
        self.assertTrue(project.colour_grading)
        self.assertTrue(project.quality_enhancement)
        self.assertTrue(project.overlays)
        self.assertTrue(project.beat_sync)
        self.assertEqual(project.reel_duration, "60_plus")
        self.assertEqual(project.wording_direction, "font_inspiration")
        self.assertEqual(project.order.kind, "custom")
        detail = browser.get(f"/client/projects/{project.id}/")
        self.assertNotContains(detail, "Upload font inspiration")

    def test_new_order_shows_three_plan_slots_and_custom_option(self):
        response = self.auth(self.owner).get("/client/new-order/")
        self.assertEqual(response.status_code, 200)
        for label in ["Plan 1", "Plan 2", "Plan 3", "Customize my edit"]:
            self.assertContains(response, label)
        for label in ["Colour grading", "Quality enhancement", "Add overlays", "Beat sync"]:
            self.assertContains(response, label)

    def test_custom_fields_render_hidden_until_custom_is_selected(self):
        browser = self.auth(self.owner)
        blank = browser.get("/client/new-order/?new=1")
        self.assertContains(blank, "data-custom-fields hidden", html=False)
        self.assertContains(blank, "data-standard-upload-fields hidden", html=False)
        self.assertContains(blank, "data-brief-fields hidden", html=False)
        self.assertContains(blank, "data-submit-row hidden", html=False)
        self.assertContains(blank, "custom-fields is-hidden", html=False)

        custom = browser.post(
            "/client/new-order/?new=1",
            {"order_choice": "custom", "song_choice": "suggest"},
        )
        self.assertEqual(custom.status_code, 200)
        self.assertContains(custom, "data-custom-fields", html=False)
        self.assertNotContains(custom, "data-custom-fields hidden", html=False)
        self.assertContains(custom, "data-standard-upload-fields hidden", html=False)
        self.assertContains(custom, "data-brief-fields", html=False)
        self.assertNotContains(custom, "data-brief-fields hidden", html=False)
        self.assertContains(custom, "data-submit-row", html=False)
        self.assertNotContains(custom, "data-submit-row hidden", html=False)

    def test_new_order_shows_clip_and_inspiration_uploads_with_bottom_save_action(self):
        response = self.auth(self.owner).get("/client/new-order/")
        self.assertContains(response, "Other Instructions")
        self.assertContains(response, "Upload Your Clips")
        self.assertContains(response, "Add Inspiration Reel/Video")
        self.assertContains(response, "Inspiration link")
        self.assertContains(response, "Max uploads: 3.")
        self.assertContains(response, 'id="upload-clips"', html=False)
        self.assertContains(response, 'id="upload-inspiration"', html=False)
        self.assertContains(response, 'multiple', html=False)
        self.assertContains(response, "Save and Proceed")
        self.assertNotContains(response, "Talk to an editor before editing")
        self.assertNotContains(response, "Talk to an editor after the draft")
        content = response.content.decode()
        self.assertLess(content.index("Upload Your Clips"), content.index("Add Inspiration Reel/Video"))
        self.assertLess(content.index("Inspiration link"), content.rindex("Add Inspiration Reel/Video"))

    def test_standard_plan_shows_only_its_upload_panel_when_resumed(self):
        plan = Plan.objects.create(
            slot=1,
            name="Standard upload plan",
            price_minor=10000,
            currency="INR",
            features=["Cuts"],
            revision_limit=1,
            delivery_hours=24,
            duration_limit_seconds=60,
            priority=1,
            active=True,
        )
        browser = self.auth(self.owner)
        saved = browser.post(
            "/client/new-order/?new=1",
            {
                "title": "Named standard project",
                "order_choice": f"plan:{plan.id}",
                "pricing_period": "per_reel",
            },
        )
        self.assertEqual(saved.status_code, 302)
        self.assertTrue(
            Project.objects.filter(client__user=self.owner, title="Named standard project").exists()
        )

        resumed = browser.get("/client/new-order/")
        self.assertContains(resumed, "data-standard-upload-fields", html=False)
        self.assertNotContains(resumed, "data-standard-upload-fields hidden", html=False)
        self.assertContains(resumed, "data-custom-fields hidden", html=False)
        self.assertContains(resumed, 'id="standard-project-title"', html=False)
        self.assertContains(resumed, 'value="Named standard project"', html=False)
        self.assertContains(resumed, 'id="standard-upload-clips"', html=False)
        self.assertContains(resumed, 'id="standard-upload-inspiration"', html=False)
        self.assertContains(resumed, "Max uploads: 3.")

    def test_invalid_submission_preserves_all_brief_values_and_validates_inspiration_url(self):
        browser = self.auth(self.owner)
        data = {
            "title": "Preserve this title",
            "order_choice": "custom",
            "requirements": "Preserve these edit instructions",
            "colour_grading": "on",
            "quality_enhancement": "on",
            "overlays": "on",
            "beat_sync": "on",
            "wants_wording": "on",
            "wording_direction": "own_font",
            "font_name": "Montserrat",
            "reference_notes": "Preserve these notes",
            "song_choice": "provide",
            "revisions_needed": "3-4",
            "song_information": "Preserve this licensed song",
            "inspiration_link": "not-a-url",
        }
        response = browser.post("/client/new-order/?new=1", data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter a valid URL")
        for value in [
            data["title"],
            data["requirements"],
            data["font_name"],
            data["reference_notes"],
            data["song_information"],
            data["inspiration_link"],
        ]:
            self.assertContains(response, value)
        self.assertContains(response, 'value="own_font" selected', html=False)
        self.assertContains(response, 'value="3-4" selected', html=False)
        self.assertContains(response, 'id="id_colour_grading" checked', html=False)
        self.assertFalse(Project.objects.filter(title=data["title"]).exists())

    def test_invalid_ajax_submission_returns_field_errors_without_redirecting(self):
        response = self.auth(self.owner).post(
            "/client/new-order/?new=1",
            {
                "title": "Keep this AJAX state",
                "order_choice": "custom",
                "song_choice": "provide",
                "song_information": "Keep this song",
                "revisions_needed": "5+",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["errors"]["reel_duration"],
            ["Choose the expected reel duration."],
        )
        self.assertFalse(Project.objects.filter(title="Keep this AJAX state").exists())

    def test_revisions_needed_is_saved_without_changing_quote_navigation(self):
        browser = self.auth(self.owner)
        form_page = browser.get("/client/new-order/?new=1")
        content = form_page.content.decode()
        self.assertLess(
            content.index('<option value="0">0</option>'),
            content.index('<option value="1-2"'),
        )
        response = browser.post(
            "/client/new-order/?new=1",
            {
                "title": "Revision preference brief",
                "order_choice": "custom",
                "reel_duration": "30_50",
                "song_choice": "suggest",
                "revisions_needed": "0",
            },
        )
        project = Project.objects.get(title="Revision preference brief")
        self.assertEqual(project.revisions_needed, "0")
        self.assertRedirects(
            response,
            f"/orders/{project.id}/",
            fetch_redirect_response=False,
        )

    def test_inspiration_link_persists_with_saved_brief(self):
        browser = self.auth(self.owner)
        link = "https://www.youtube.com/watch?v=synthetic-reference"
        response = browser.post(
            "/client/new-order/?new=1",
            {
                "title": "Linked inspiration",
                "order_choice": "custom",
                "reel_duration": "30_50",
                "song_choice": "suggest",
                "inspiration_link": link,
            },
        )
        project = Project.objects.get(title="Linked inspiration")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(project.inspiration_link, link)
        self.assertContains(browser.get("/client/new-order/"), link)

    def test_new_order_ignores_removed_consultation_fields(self):
        browser = self.auth(self.owner)
        response = browser.post(
            "/client/new-order/?new=1",
            {
                "title": "No consultation options",
                "order_choice": "custom",
                "reel_duration": "30_50",
                "song_choice": "suggest",
                "call_before": "on",
                "call_after": "on",
            },
        )
        project = Project.objects.get(title="No consultation options")
        self.assertRedirects(
            response,
            f"/orders/{project.id}/",
            fetch_redirect_response=False,
        )
        self.assertFalse(project.call_before)
        self.assertFalse(project.call_after)

    def test_song_details_are_hidden_by_default_and_cleared_for_suggestions(self):
        browser = self.auth(self.owner)
        response = browser.get("/client/new-order/?new=1")
        self.assertContains(response, "Song Name or Link")
        self.assertContains(response, "data-song-details hidden", html=False)

        saved = browser.post(
            "/client/new-order/?new=1",
            {
                "title": "Suggested music brief",
                "order_choice": "custom",
                "reel_duration": "30_50",
                "song_choice": "suggest",
                "song_information": "This must not be saved",
            },
        )
        project = Project.objects.get(title="Suggested music brief")
        self.assertRedirects(
            saved,
            f"/orders/{project.id}/",
            fetch_redirect_response=False,
        )
        self.assertEqual(project.song_information, "")

    def test_saved_brief_remains_populated_until_create_new_is_clicked(self):
        browser = self.auth(self.owner)
        response = browser.post(
            "/client/new-order/?new=1",
            {
                "title": "Persistent brief",
                "order_choice": "custom",
                "reel_duration": "30_50",
                "requirements": "Keep this exact direction",
                "reference_notes": "Use the quiet ending",
                "song_choice": "provide",
                "song_information": "Licensed track",
            },
        )
        project = Project.objects.get(title="Persistent brief")
        self.assertRedirects(
            response,
            f"/orders/{project.id}/",
            fetch_redirect_response=False,
        )

        resumed = browser.get("/client/new-order/")
        self.assertContains(resumed, "Persistent brief")
        self.assertContains(resumed, "Keep this exact direction")
        self.assertContains(resumed, "Use the quiet ending")
        self.assertContains(resumed, "Create New")
        self.assertContains(resumed, 'value="custom" required checked', html=False)

        blank = browser.get("/client/new-order/?new=1")
        self.assertNotContains(blank, "Persistent brief")
        self.assertNotContains(blank, "Keep this exact direction")
        self.assertNotContains(blank, "Use the quiet ending")

    def test_completed_brief_uploads_remain_project_scoped_and_visible(self):
        browser = self.auth(self.owner)
        fixtures = [
            ("camera-original.mp4", "video/mp4", "source"),
            ("storyboard.pdf", "application/pdf", "source"),
            ("inspiration.mov", "video/quicktime", "reference"),
        ]
        saved_files = []
        for position, (filename, content_type, category) in enumerate(fixtures, start=1):
            saved_files.append(
                File.objects.create(
                    project=self.project,
                    uploader=self.owner,
                    filename=filename,
                    object_key=f"private/brief/{self.project.id}/{position}",
                    size_bytes=position * 100,
                    sha256=str(position) * 64,
                    content_type=content_type,
                    category=category,
                    state="ready",
                    storage_version=f"v{position}",
                    expires_at=timezone.now(),
                    completed_at=timezone.now(),
                )
            )

        other_project = Project.objects.create(client=self.profile, title="Other project")
        Order.objects.create(project=other_project)
        File.objects.create(
            project=other_project,
            uploader=self.owner,
            filename="other-project-only.pdf",
            object_key=f"private/brief/{other_project.id}/1",
            size_bytes=25,
            sha256="f" * 64,
            content_type="application/pdf",
            category="source",
            state="ready",
            storage_version="other-v1",
            expires_at=timezone.now(),
            completed_at=timezone.now(),
        )

        detail = browser.get(f"/client/projects/{self.project.id}/")
        edit = browser.get(f"/client/projects/{self.project.id}/edit/")
        api = browser.get(f"/api/projects/{self.project.id}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(edit.status_code, 200)
        self.assertEqual(api.status_code, 200)
        self.assertContains(edit, "Previously uploaded files")
        for saved_file in saved_files:
            self.assertContains(detail, saved_file.filename)
            self.assertContains(edit, saved_file.filename)
            self.assertEqual(
                sum(item.id == saved_file.id for item in detail.context["files"]),
                1,
            )
        self.assertNotContains(detail, "other-project-only.pdf")
        self.assertNotContains(edit, "other-project-only.pdf")
        self.assertEqual(
            [item["id"] for item in api.json()["files"]],
            [str(saved_file.id) for saved_file in saved_files],
        )
        self.assertEqual(
            [item["category"] for item in api.json()["files"]],
            [saved_file.category for saved_file in saved_files],
        )

        added_file = File.objects.create(
            project=self.project,
            uploader=self.owner,
            filename="added-on-edit.webp",
            object_key=f"private/brief/{self.project.id}/added",
            size_bytes=400,
            sha256="a" * 64,
            content_type="image/webp",
            category="source",
            state="ready",
            storage_version="added-v1",
            expires_at=timezone.now(),
            completed_at=timezone.now(),
        )
        refreshed = browser.get(f"/client/projects/{self.project.id}/edit/")
        for saved_file in [*saved_files, added_file]:
            self.assertContains(refreshed, saved_file.filename)

    @patch("core.views.delete_private_object_versions", return_value=1)
    def test_client_can_remove_own_unpaid_brief_file_without_deleting_record(self, delete_versions):
        browser = self.auth(self.owner)
        file = File.objects.create(
            project=self.project,
            uploader=self.owner,
            filename="removable-reference.mp4",
            object_key=f"private/brief/{self.project.id}/removable",
            size_bytes=100,
            sha256="a" * 64,
            content_type="video/mp4",
            category="reference",
            state="ready",
            storage_version="v1",
            expires_at=timezone.now(),
            completed_at=timezone.now(),
        )
        edit = browser.get(f"/client/projects/{self.project.id}/edit/")
        self.assertContains(edit, "removable-reference.mp4")
        self.assertContains(edit, "Remove")
        response = browser.post(f"/api/files/{file.id}/remove/")
        self.assertEqual(response.status_code, 200)
        delete_versions.assert_called_once_with(file.object_key)
        file.refresh_from_db()
        self.assertEqual(file.state, "removed")
        self.assertNotContains(
            browser.get(f"/client/projects/{self.project.id}/edit/"),
            "removable-reference.mp4",
        )
        self.assertTrue(
            AuditLog.objects.filter(
                action="file.removed_from_brief", actor=self.owner, target_id=str(file.id)
            ).exists()
        )
        self.assertEqual(
            self.auth(self.other).post(f"/api/files/{file.id}/remove/").status_code,
            404,
        )

    @patch("core.views.delete_private_object_versions")
    def test_storage_failure_leaves_brief_file_active_and_returns_specific_error(self, delete_versions):
        delete_versions.side_effect = ClientError(
            {"Error": {"Code": "ServiceUnavailable", "Message": "synthetic"}},
            "ListObjectVersions",
        )
        file = File.objects.create(
            project=self.project,
            uploader=self.owner,
            filename="retained-reference.mp4",
            object_key=f"private/brief/{self.project.id}/retained",
            size_bytes=100,
            sha256="a" * 64,
            content_type="video/mp4",
            category="reference",
            state="ready",
            storage_version="v1",
            expires_at=timezone.now(),
            completed_at=timezone.now(),
        )

        response = self.auth(self.owner).post(f"/api/files/{file.id}/remove/")

        self.assertEqual(response.status_code, 503)
        self.assertIn("could not be removed from storage", response.json()["error"])
        file.refresh_from_db()
        self.assertEqual(file.state, "ready")

    @patch("core.views.upload_permission", return_value={"method": "PUT", "url": "private", "headers": {}})
    def test_removed_reference_frees_one_of_three_server_enforced_slots(self, _permission):
        browser = self.auth(self.owner)
        files = []
        for number in range(3):
            files.append(
                File.objects.create(
                    project=self.project,
                    uploader=self.owner,
                    filename=f"reference-{number}.mp4",
                    object_key=f"private/brief/{self.project.id}/reference-{number}",
                    size_bytes=100,
                    sha256=str(number + 1) * 64,
                    content_type="video/mp4",
                    category="reference",
                    state="ready",
                    storage_version=f"v{number}",
                    expires_at=timezone.now(),
                    completed_at=timezone.now(),
                )
            )
        upload_url = f"/api/projects/{self.project.id}/uploads/"
        payload = {**self.upload_data(), "category": "reference"}
        self.assertEqual(self.post_json(browser, upload_url, payload).status_code, 409)
        self.assertEqual(browser.post(f"/api/files/{files[0].id}/remove/").status_code, 200)
        self.assertEqual(self.post_json(browser, upload_url, payload).status_code, 201)

    def test_font_selection_requires_and_persists_own_font_name(self):
        browser = self.auth(self.owner)
        data = {
            "title": "Typography brief",
            "order_choice": "custom",
            "reel_duration": "30_50",
            "wants_wording": "on",
            "wording_direction": "own_font",
            "song_choice": "suggest",
        }
        missing = browser.post("/client/new-order/?new=1", data)
        self.assertEqual(missing.status_code, 200)
        self.assertContains(missing, "Enter the font style or name")

        saved = browser.post("/client/new-order/?new=1", {**data, "font_name": "Montserrat"})
        project = Project.objects.get(title="Typography brief")
        self.assertRedirects(
            saved,
            f"/orders/{project.id}/",
            fetch_redirect_response=False,
        )
        self.assertEqual(project.font_name, "Montserrat")
        form_page = browser.get("/client/new-order/")
        self.assertContains(form_page, "Describe the edit")
        self.assertContains(form_page, "Font selection")
        self.assertContains(form_page, "data-font-inspiration hidden", html=False)
        self.assertContains(form_page, "Click to Upload")
        self.assertContains(form_page, 'accept="image/*"', html=False)
        self.assertNotContains(form_page, "Inspiration and reference notes")

    def test_owner_can_edit_saved_creative_brief_without_creating_another_project(self):
        browser = self.auth(self.owner)
        detail = browser.get(f"/client/projects/{self.project.id}/")
        self.assertContains(detail, f'/client/projects/{self.project.id}/edit/')
        project_count = Project.objects.count()

        response = browser.post(
            f"/client/projects/{self.project.id}/edit/",
            {
                "title": "Updated brief",
                "order_choice": "custom",
                "reel_duration": "60_plus",
                "requirements": "Updated creative direction",
                "song_choice": "suggest",
            },
        )
        self.assertRedirects(
            response,
            f"/orders/{self.project.id}/",
            fetch_redirect_response=False,
        )
        self.project.refresh_from_db()
        self.assertEqual(self.project.title, "Updated brief")
        self.assertEqual(self.project.requirements, "Updated creative direction")
        self.assertEqual(Project.objects.count(), project_count)
        self.assertTrue(
            AuditLog.objects.filter(
                action="project.brief_updated", actor=self.owner, target_id=str(self.project.id)
            ).exists()
        )

        self.assertEqual(
            self.auth(self.other).get(f"/client/projects/{self.project.id}/edit/").status_code,
            404,
        )

    def test_available_plan_selection_is_persisted_and_custom_fields_are_rejected(self):
        plan = Plan.objects.create(
            slot=1,
            name="Synthetic plan",
            price_minor=10000,
            currency="INR",
            features=["Cuts"],
            revision_limit=1,
            delivery_hours=24,
            duration_limit_seconds=60,
            priority=1,
            active=True,
        )
        browser = self.auth(self.owner)
        rejected = browser.post(
            "/client/new-order/",
            {
                "title": "Tampered plan",
                "order_choice": f"plan:{plan.id}",
                "colour_grading": "on",
                "song_choice": "suggest",
            },
        )
        self.assertEqual(rejected.status_code, 200)
        self.assertContains(rejected, "Choose Customize my edit")
        response = browser.post(
            "/client/new-order/",
            {
                "title": "Plan order",
                "order_choice": f"plan:{plan.id}",
                "song_choice": "suggest",
            },
        )
        self.assertEqual(response.status_code, 302)
        order = Project.objects.get(title="Plan order").order
        self.assertEqual(order.kind, "plan")
        self.assertEqual(order.plan, plan)

        no_hidden_brief_fields = browser.post(
            "/client/new-order/?new=1",
            {
                "order_choice": f"plan:{plan.id}",
                "pricing_period": "per_reel",
            },
        )
        generated_project = Project.objects.get(title="Synthetic plan")
        self.assertRedirects(
            no_hidden_brief_fields, f"/client/projects/{generated_project.id}/"
        )
        self.assertEqual(generated_project.order.plan, plan)

    def test_monthly_and_yearly_pricing_are_locked_to_per_reel(self):
        plan = Plan.objects.create(
            slot=1,
            name="Period plan",
            price_minor=10000,
            monthly_price_minor=90000,
            yearly_price_minor=900000,
            currency="INR",
            features=["Cuts"],
            revision_limit=1,
            delivery_hours=24,
            duration_limit_seconds=60,
            priority=1,
            active=True,
        )
        browser = self.auth(self.owner)
        form_page = browser.get("/client/new-order/?new=1")
        self.assertContains(form_page, "Per Reel")
        self.assertContains(form_page, "Monthly")
        self.assertContains(form_page, "Yearly")
        self.assertContains(form_page, "Upcoming", count=2)
        self.assertContains(form_page, "More info")
        self.assertNotContains(form_page, "&#128274;", html=False)
        self.assertContains(form_page, 'value="per_reel" checked', html=False)
        self.assertContains(form_page, 'data-price-per-reel="₹100.00"', html=False)
        self.assertNotContains(form_page, 'value="monthly"', html=False)
        self.assertNotContains(form_page, 'value="yearly"', html=False)
        self.assertNotContains(form_page, "Monthly creator plans")
        self.assertNotContains(form_page, "Recurring editing packages")
        self.assertNotContains(form_page, "Monthly plans are being configured")

        for period in [Plan.PricingPeriod.MONTHLY, Plan.PricingPeriod.YEARLY]:
            with self.subTest(period=period):
                forged_title = f"Forged {period} period"
                rejected = browser.post(
                    "/client/new-order/?new=1",
                    {
                        "title": forged_title,
                        "order_choice": f"plan:{plan.id}",
                        "pricing_period": period,
                        "song_choice": "suggest",
                    },
                )
                self.assertEqual(rejected.status_code, 200)
                self.assertContains(rejected, "Monthly and yearly pricing are upcoming")
                self.assertFalse(Project.objects.filter(title=forged_title).exists())

        saved = browser.post(
            "/client/new-order/?new=1",
            {
                "title": "Per reel plan brief",
                "order_choice": f"plan:{plan.id}",
                "pricing_period": "per_reel",
                "song_choice": "suggest",
            },
        )
        project = Project.objects.get(title="Per reel plan brief")
        self.assertRedirects(saved, f"/client/projects/{project.id}/")
        self.assertEqual(project.order.plan, plan)
        self.assertEqual(project.order.pricing_period, Plan.PricingPeriod.PER_REEL)
        detail = browser.get(f"/client/projects/{project.id}/")
        self.assertContains(detail, "Period plan · Per Reel")
        edit = browser.get(f"/client/projects/{project.id}/edit/")
        self.assertContains(edit, 'value="per_reel" checked', html=False)

        custom = browser.post(
            "/client/new-order/?new=1",
            {
                "title": "Custom ignores toggle",
                "order_choice": "custom",
                "pricing_period": "per_reel",
                "reel_duration": "30_50",
                "song_choice": "suggest",
            },
        )
        custom_project = Project.objects.get(title="Custom ignores toggle")
        self.assertRedirects(
            custom,
            f"/orders/{custom_project.id}/",
            fetch_redirect_response=False,
        )
        self.assertEqual(custom_project.order.kind, "custom")
        self.assertEqual(custom_project.order.pricing_period, Plan.PricingPeriod.PER_REEL)

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
            {"sha256": "bad"},
            {"size_bytes": -1},
        ]:
            self.assertEqual(self.post_json(browser, url, {**self.upload_data(), **changes}).status_code, 400)
        self.assertEqual(
            self.post_json(browser, url, {**self.upload_data(), "category": "final"}).status_code, 403
        )
        self.assertEqual(
            self.post_json(
                browser, url, {**self.upload_data(), "category": "font_reference"}
            ).status_code,
            403,
        )
        self.assertEqual(self.post_json(self.auth(self.other), url, self.upload_data()).status_code, 404)

    @patch("core.views.upload_permission", return_value={"method": "PUT", "url": "private", "headers": {}})
    def test_font_and_inspiration_upload_rules_are_enforced(self, _permission):
        browser = self.auth(self.owner)
        self.project.wants_wording = True
        self.project.wording_direction = "font_inspiration"
        self.project.save(update_fields=["wants_wording", "wording_direction", "updated_at"])
        UploadPolicy.objects.filter(pk=1).update(max_bytes=2 * 1024 * 1024)
        url = f"/api/projects/{self.project.id}/uploads/"
        base = {**self.upload_data(), "category": "font_reference"}

        for filename, content_type, size in [
            ("font.pdf", "application/pdf", 500),
            ("font.doc", "application/msword", 500),
            ("font.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", 500),
            ("font.png", "image/png", 1024 * 1024),
        ]:
            response = self.post_json(
                browser,
                url,
                {**base, "filename": filename, "content_type": content_type, "size_bytes": size},
            )
            self.assertEqual(response.status_code, 400)
        accepted_font = self.post_json(
            browser,
            url,
            {**base, "filename": "font.webp", "content_type": "image/webp", "size_bytes": 900000},
        )
        self.assertEqual(accepted_font.status_code, 201)

        arbitrary_clip = self.post_json(
            browser,
            url,
            {
                **self.upload_data(),
                "filename": "clip.uncommon",
                "content_type": "application/octet-stream",
                "category": "source",
            },
        )
        self.assertEqual(arbitrary_clip.status_code, 201)

        arbitrary_reference = {
            **self.upload_data(),
            "filename": "inspiration.uncommon",
            "content_type": "application/octet-stream",
            "category": "reference",
        }
        for _ in range(3):
            self.assertEqual(self.post_json(browser, url, arbitrary_reference).status_code, 201)
        fourth = self.post_json(browser, url, arbitrary_reference)
        self.assertEqual(fourth.status_code, 409)
        self.assertEqual(fourth.json()["error"], "Max uploads: 3")

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
