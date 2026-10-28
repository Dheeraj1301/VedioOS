from unittest.mock import Mock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from core.landing_content import FAQ_DEFAULTS, LANDING_DEFAULTS
from core.models import LandingPageSettings, User


class LandingPageTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="landing-admin@example.test", password="ValidPass!123", name="Landing Admin", role="admin"
        )
        self.client_user = User.objects.create_user(
            email="landing-client@example.test",
            password="ValidPass!123",
            name="Landing Client",
            role="client",
        )

    def landing_form_data(self, faqs=None, **overrides):
        faqs = list(faqs if faqs is not None else FAQ_DEFAULTS)
        data = {
            **LANDING_DEFAULTS,
            "faqs-TOTAL_FORMS": str(len(faqs)),
            "faqs-INITIAL_FORMS": str(len(faqs)),
            "faqs-MIN_NUM_FORMS": "0",
            "faqs-MAX_NUM_FORMS": "50",
        }
        for index, faq in enumerate(faqs):
            data.update(
                {
                    f"faqs-{index}-id": faq.get("id", ""),
                    f"faqs-{index}-title": faq["title"],
                    f"faqs-{index}-content": faq["content"],
                    f"faqs-{index}-ORDER": str(index + 1),
                }
            )
            if faq.get("published", False):
                data[f"faqs-{index}-published"] = "on"
        data.update(overrides)
        return data

    def test_defaults_preserve_existing_landing_page(self):
        response = self.client.get("/")
        self.assertContains(response, 'class="landing-page"')
        self.assertContains(response, "You shoot.")
        self.assertContains(response, "Made by people.")
        self.assertContains(response, "Does AI edit my video?")
        self.assertContains(response, "Contact Us")
        self.assertContains(response, "open Support in your workspace")
        self.assertNotContains(response, "landing-hero-video")

    def test_only_admin_can_open_landing_controls(self):
        self.client.force_login(self.client_user)
        self.assertEqual(self.client.get("/admin/landing-page/").status_code, 403)
        self.client.force_login(self.admin)
        response = self.client.get("/admin/landing-page/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Every visible landing-page label")
        self.assertContains(response, "Hero heading line 1")
        self.assertContains(response, "Contact Us")
        self.assertContains(response, "Create, edit, reorder, publish, or remove")

    def test_admin_copy_changes_render_escaped_without_changing_links(self):
        self.client.force_login(self.admin)
        data = self.landing_form_data(hero_line_1="A safer <script>alert(1)</script> edit.")
        response = self.client.post("/admin/landing-page/", data)
        self.assertRedirects(response, "/admin/landing-page/")
        page = self.client.get("/")
        self.assertContains(page, "A safer &lt;script&gt;alert(1)&lt;/script&gt; edit.")
        self.assertContains(page, 'href="/register/"')
        self.assertNotContains(page, 'href="#how-it-works"')
        self.assertNotContains(page, 'href="/#how-it-works"')
        self.assertContains(page, 'href="/#services"')

    @patch("core.landing_views.storage_client")
    def test_admin_can_upload_private_looping_mp4(self, storage_client):
        storage = Mock()
        storage.put_object.return_value = {"VersionId": "version-1"}
        storage_client.return_value = storage
        upload = SimpleUploadedFile("showreel.mp4", b"\x00\x00\x00\x18ftypisom0000", content_type="video/mp4")
        self.client.force_login(self.admin)
        response = self.client.post("/admin/landing-page/", self.landing_form_data(hero_video=upload))
        self.assertRedirects(response, "/admin/landing-page/")
        config = LandingPageSettings.objects.get(pk=1)
        self.assertTrue(config.hero_video_object_key.startswith("landing/hero/"))
        self.assertEqual(config.hero_video_storage_version, "version-1")
        self.assertEqual(config.hero_video_content_type, "video/mp4")
        page = self.client.get("/")
        self.assertContains(page, "landing-hero-video")
        self.assertContains(page, "autoplay muted loop playsinline")

    def test_non_mp4_upload_is_rejected(self):
        self.client.force_login(self.admin)
        upload = SimpleUploadedFile("wrong.mp4", b"not-a-video", content_type="video/mp4")
        response = self.client.post("/admin/landing-page/", self.landing_form_data(hero_video=upload))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "not a valid MP4")
        self.assertFalse(LandingPageSettings.objects.exists())

    @patch("core.landing_views.storage_client")
    def test_admin_can_remove_video_without_changing_copy(self, storage_client):
        storage = Mock()
        storage_client.return_value = storage
        LandingPageSettings.objects.create(
            content={"hero_line_1": "Saved heading"},
            hero_video_object_key="landing/hero/old.mp4",
            hero_video_storage_version="old-version",
            hero_video_filename="old.mp4",
            hero_video_content_type="video/mp4",
            hero_video_size_bytes=12,
            hero_video_sha256="a" * 64,
        )
        self.client.force_login(self.admin)
        response = self.client.post(
            "/admin/landing-page/",
            self.landing_form_data(hero_line_1="Saved heading", remove_hero_video="on"),
        )
        self.assertRedirects(response, "/admin/landing-page/")
        config = LandingPageSettings.objects.get(pk=1)
        self.assertEqual(config.hero_video_object_key, "")
        self.assertEqual(config.content["hero_line_1"], "Saved heading")
        storage.delete_object.assert_called_once_with(
            Bucket=storage_client.return_value.delete_object.call_args.kwargs["Bucket"],
            Key="landing/hero/old.mp4",
            VersionId="old-version",
        )

    @patch("core.landing_views.landing_video_permission", return_value="https://private.example/signed")
    def test_public_video_route_uses_fresh_signed_address(self, permission):
        config = LandingPageSettings.objects.create(
            content={}, hero_video_object_key="landing/hero/current.mp4"
        )
        response = self.client.get("/landing/hero-video/")
        self.assertRedirects(response, "https://private.example/signed", fetch_redirect_response=False)
        permission.assert_called_once_with(config)

    def test_video_route_is_not_present_without_published_video(self):
        self.assertEqual(self.client.get("/landing/hero-video/").status_code, 404)

    def test_legacy_saved_faq_copy_is_preserved_and_contact_is_added(self):
        LandingPageSettings.objects.create(
            content={"faq_1_question": "Legacy question", "faq_1_answer": "Legacy answer"}
        )
        page = self.client.get("/")
        self.assertContains(page, "Legacy question")
        self.assertContains(page, "Legacy answer")
        self.assertContains(page, "Contact Us")

    def test_admin_can_create_edit_delete_reorder_and_unpublish_faqs(self):
        faqs = [
            {
                "id": "contact-us",
                "title": "Talk to BRIO",
                "content": "Email hello@example.test",
                "published": True,
            },
            {"id": "hidden", "title": "Hidden question", "content": "Hidden answer", "published": False},
            {"id": "new", "title": "New question", "content": "New answer", "published": True},
        ]
        self.client.force_login(self.admin)
        response = self.client.post("/admin/landing-page/", self.landing_form_data(faqs))
        self.assertRedirects(response, "/admin/landing-page/")

        config = LandingPageSettings.objects.get(pk=1)
        self.assertEqual(
            [item["title"] for item in config.content["faqs"]],
            ["Talk to BRIO", "Hidden question", "New question"],
        )
        page = self.client.get("/")
        self.assertContains(page, "Talk to BRIO")
        self.assertContains(page, "Email hello@example.test")
        self.assertContains(page, "New question")
        self.assertNotContains(page, "Hidden question")
        self.assertNotContains(page, "Does AI edit my video?")

        reordered = [faqs[2], faqs[0]]
        response = self.client.post("/admin/landing-page/", self.landing_form_data(reordered))
        self.assertRedirects(response, "/admin/landing-page/")
        config.refresh_from_db()
        self.assertEqual([item["id"] for item in config.content["faqs"]], ["new", "contact-us"])
