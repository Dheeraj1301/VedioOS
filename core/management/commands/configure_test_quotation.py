from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.commerce_forms import PolicyForm
from core.models import CommercePolicy, QuotationFeature


class Command(BaseCommand):
    help = "Persist an explicitly test-only weighted quotation policy for end-to-end checkout testing."

    def add_arguments(self, parser):
        parser.add_argument("--confirm-test-only", action="store_true")
        parser.add_argument("--base-minor", type=int, required=True)
        parser.add_argument("--point-minor", type=int, required=True)
        parser.add_argument("--minimum-minor", type=int, required=True)
        parser.add_argument("--maximum-minor", type=int, required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        if not options["confirm_test_only"]:
            raise CommandError("Pass --confirm-test-only to acknowledge these are synthetic test values.")
        if not settings.DEBUG or settings.PAYMENT_MODE not in {"sandbox", "razorpay_test"}:
            raise CommandError("Test quotation setup requires DEBUG and a test payment gateway.")
        expected = {value for value, _label in QuotationFeature.Code.choices}
        configured = set(QuotationFeature.objects.filter(code__in=expected).values_list("code", flat=True))
        if configured != expected:
            raise CommandError("All seven quotation feature score rows must exist before setup.")
        values = {
            "pricing_context": CommercePolicy.PricingContext.TEST,
            "currency": "INR",
            "custom_base_minor": options["base_minor"],
            "custom_revision_limit": 2,
            "custom_delivery_hours": 24,
            "custom_duration_limit_seconds": 600,
            "custom_priority": 1,
            "quotation_engine_enabled": True,
            "quotation_time_weight": 40,
            "quotation_importance_weight": 20,
            "quotation_complexity_weight": 40,
            "quotation_point_minor": options["point_minor"],
            "quotation_min_minor": options["minimum_minor"],
            "quotation_max_minor": options["maximum_minor"],
            "terms": "TEST ONLY — synthetic quotation for checkout verification; not a commercial offer.",
            "delivery_terms": "TEST ONLY — delivery timing is not a production promise.",
            "refund_terms": "TEST ONLY — no real money is charged or refundable.",
            "tax_terms": "TEST ONLY — no tax invoice is issued.",
            "quotes_enabled": True,
            "review_rule": "",
        }
        instance = CommercePolicy.objects.filter(pk=1).first() or CommercePolicy(pk=1)
        form = PolicyForm(values, instance=instance, values_are_minor=True)
        if not form.is_valid():
            raise CommandError(f"Test quotation configuration is invalid: {form.errors.as_json()}")
        form.save()
        self.stdout.write(
            self.style.SUCCESS(
                "Test-only weighted quotation enabled. Replace it with owner-approved Production pricing before launch."
            )
        )
