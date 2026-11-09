import re
from pathlib import Path

from django.conf import settings
from django.test import TestCase, override_settings

from core.middleware import content_security_policy


class ContentSecurityPolicyTests(TestCase):
    def test_every_page_sends_a_strict_policy(self):
        for path in ["/", "/login/", "/register/", "/api/areas/client/"]:
            policy = self.client.get(path)["Content-Security-Policy"]
            directives = dict(part.split(" ", 1) for part in policy.split("; "))
            self.assertEqual(
                directives["script-src"],
                "'self' 'wasm-unsafe-eval' https://checkout.razorpay.com",
            )
            self.assertEqual(directives["object-src"], "'none'")
            self.assertEqual(directives["frame-ancestors"], "'none'")
            self.assertNotIn("unsafe-inline", policy)
            self.assertNotIn("'unsafe-eval'", directives["script-src"].split())

    def test_wasm_hashing_does_not_enable_javascript_eval(self):
        directives = dict(
            part.split(" ", 1) for part in content_security_policy().split("; ")
        )
        script_sources = directives["script-src"].split()
        self.assertIn("'wasm-unsafe-eval'", script_sources)
        self.assertNotIn("'unsafe-eval'", script_sources)

    @override_settings(S3_ENDPOINT_URL="https://s3.ap-southeast-2.amazonaws.com", PRIVATE_STORAGE_ENABLED=True)
    def test_private_storage_origin_is_allowed_for_uploads_and_media(self):
        policy = content_security_policy()
        for directive in ["connect-src", "media-src", "img-src"]:
            self.assertRegex(policy, rf"{directive} [^;]*https://s3\.ap-southeast-2\.amazonaws\.com")

    @override_settings(PRIVATE_STORAGE_ENABLED=False)
    def test_disabled_storage_adds_no_storage_origin(self):
        self.assertNotIn(settings.S3_ENDPOINT_URL, content_security_policy())

    def test_templates_have_no_inline_scripts_styles_or_handlers(self):
        for template in Path(settings.BASE_DIR, "templates").rglob("*.html"):
            source = template.read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"<script(?![^>]*\bsrc=)[^>]*>", source), template)
            self.assertNotIn('style="', source, template)
            self.assertIsNone(re.search(r"\son[a-z]+=\"", source), template)

    def test_payment_checkout_policy_only_adds_razorpay_needs(self):
        strict = dict(part.split(" ", 1) for part in content_security_policy().split("; "))
        checkout = dict(part.split(" ", 1) for part in content_security_policy(payment_checkout=True).split("; "))
        self.assertEqual(checkout["script-src"], strict["script-src"] + " https://cdn.razorpay.com")
        self.assertEqual(checkout["style-src"], strict["style-src"] + " 'unsafe-inline'")
        self.assertEqual({k: v for k, v in checkout.items() if k not in {"script-src", "style-src"}},
                         {k: v for k, v in strict.items() if k not in {"script-src", "style-src"}})
        source = Path(settings.BASE_DIR, "core", "commerce_views.py").read_text(encoding="utf-8")
        self.assertEqual(source.count("content_security_policy(payment_checkout=True)"), 2)


class VercelHostTests(TestCase):
    def test_deployment_and_branch_addresses_are_allowed(self):
        import json
        import os
        import subprocess
        import sys

        env = {
            **os.environ,
            "DJANGO_SETTINGS_MODULE": "vedioos.settings",
            "VERCEL_URL": "vedioos-abc123-team.vercel.app",
            "VERCEL_BRANCH_URL": "vedioos-git-ui2-team.vercel.app",
        }
        script = "import json, vedioos.settings as s; print(json.dumps([s.ALLOWED_HOSTS, s.CSRF_TRUSTED_ORIGINS]))"
        output = subprocess.run(
            [sys.executable, "-c", script], env=env, cwd=settings.BASE_DIR, capture_output=True, text=True, check=True
        ).stdout
        hosts, origins = json.loads(output.strip().splitlines()[-1])
        for host in ["vedioos-abc123-team.vercel.app", "vedioos-git-ui2-team.vercel.app"]:
            self.assertIn(host, hosts)
            self.assertIn(f"https://{host}", origins)


class HeroVideoTests(TestCase):
    @override_settings(PRIVATE_STORAGE_ENABLED=True, S3_ENDPOINT_URL="https://s3.ap-southeast-2.amazonaws.com")
    def test_landing_puts_a_signed_hero_link_in_the_page_with_the_redirect_as_fallback(self):
        from unittest.mock import patch

        from core.models import LandingPageSettings

        LandingPageSettings.objects.update_or_create(pk=1, defaults={"hero_video_object_key": "edits/landing/hero/x.mp4"})
        with patch("core.views.landing_video_permission", return_value="https://s3.example/signed.mp4") as sign:
            page = self.client.get("/")
        sign.assert_called_once()
        self.assertEqual(sign.call_args.kwargs["expires_in"], 3600)
        self.assertContains(page, '<source src="https://s3.example/signed.mp4" type="video/mp4">')
        self.assertContains(page, '<source src="/landing/hero-video/" type="video/mp4">')
        self.assertContains(page, '<link rel="preconnect" href="https://s3.ap-southeast-2.amazonaws.com">')
        self.assertContains(page, 'preload="auto"')
