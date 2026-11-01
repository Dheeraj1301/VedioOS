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
            self.assertEqual(directives["script-src"], "'self' https://checkout.razorpay.com")
            self.assertEqual(directives["object-src"], "'none'")
            self.assertEqual(directives["frame-ancestors"], "'none'")
            self.assertNotIn("unsafe-inline", policy)
            self.assertNotIn("unsafe-eval", policy)

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
