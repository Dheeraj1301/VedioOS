import hashlib
import hmac
import json
import time
import uuid
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from core.commerce import accept_quote, create_quote, custom_estimate_result
from core.commerce_forms import PackageForm, PlanForm, PolicyForm
from core.models import (
    Client,
    CommercePolicy,
    CustomService,
    InfluencerPackage,
    Order,
    OrderQuote,
    Payment,
    PaymentEvent,
    Plan,
    Project,
    QuotationFeature,
    User,
)
from core.money import format_money
from core.payments import apply_sandbox_event, start_checkout
from operations.models import AuditLog, CallRequest, Editor, EditorProficiency, Notification

SECRET = "synthetic-sandbox-key-for-tests-only-12345"


@override_settings(DEBUG=True, PAYMENT_MODE="sandbox", SANDBOX_PAYMENT_SECRET=SECRET)
class CommerceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("commerce@example.test", "synthetic-password", name="Buyer")
        cls.other = User.objects.create_user("othercommerce@example.test", "synthetic-password", name="Other")
        cls.admin = User.objects.create_user(
            "catalog@example.test", "synthetic-password", role="admin", name="Admin"
        )
        cls.project = Project.objects.create(
            client=Client.objects.create(user=cls.user), title="Commerce test"
        )
        Client.objects.create(user=cls.other)
        cls.order = Order.objects.create(project=cls.project)
        cls.policy = CommercePolicy.objects.create(
            currency="INR",
            custom_base_minor=10000,
            custom_revision_limit=2,
            custom_delivery_hours=24,
            custom_duration_limit_seconds=60,
            custom_priority=1,
            terms="TEST service terms",
            delivery_terms="TEST delivery terms",
            refund_terms="TEST refund terms",
            tax_terms="TEST tax terms",
            quotes_enabled=True,
        )
        cls.plan = Plan.objects.create(
            slot=1,
            name="Synthetic plan",
            price_minor=25000,
            monthly_price_minor=200000,
            yearly_price_minor=2000000,
            currency="INR",
            features=["Test cuts"],
            revision_limit=2,
            delivery_hours=24,
            duration_limit_seconds=60,
            priority=1,
            active=True,
        )
        cls.service = CustomService.objects.create(
            name="Synthetic captions", price_minor=1500, currency="INR", active=True
        )
        cls.duration_service = CustomService.objects.create(
            name="Synthetic medium duration",
            code="duration_30_50",
            price_minor=2000,
            currency="INR",
            active=True,
        )
        cls.grading_service = CustomService.objects.create(
            name="Synthetic colour grading",
            code="colour_grading",
            price_minor=3000,
            currency="INR",
            active=True,
        )

    def quote(self):
        return create_quote(self.user, self.project.id, "plan", self.plan.id)

    def payment(self):
        accept_quote(self.user, self.project.id, self.quote().id)
        return start_checkout(self.user, self.project.id)

    def event(self, payment, status="confirmed", **extra):
        event = {
            "event_id": uuid.uuid4().hex,
            "reference": payment.provider_reference,
            "order_id": str(payment.order_id),
            "amount_minor": payment.amount_minor,
            "currency": payment.currency,
            "status": status,
            **extra,
        }
        body = json.dumps(event).encode()
        stamp = str(int(time.time()))
        signature = (
            stamp + "." + hmac.new(SECRET.encode(), stamp.encode() + b"." + body, hashlib.sha256).hexdigest()
        )
        return body, signature

    def test_custom_quote_server_total_and_deduplicated_services(self):
        quote = create_quote(
            self.user, self.project.id, "custom", service_ids=[self.service.id, self.service.id]
        )
        self.assertEqual(quote.total_minor, 11500)
        self.assertEqual(len(quote.snapshot["items"]), 2)

    def test_custom_estimate_and_quote_use_mapped_server_prices(self):
        self.client.force_login(self.user)
        response = self.client.post(
            "/api/custom-estimate/",
            json.dumps(
                {
                    "colour_grading": True,
                    "quality_enhancement": False,
                    "reel_duration": "30_50",
                    "wants_wording": False,
                    "wording_direction": "",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total_minor"], 15000)
        self.assertEqual(response.json()["display_total"], "₹150.00")
        self.project.colour_grading = True
        self.project.reel_duration = "30_50"
        self.project.save(update_fields=["colour_grading", "reel_duration", "updated_at"])
        quote = create_quote(
            self.user, self.project.id, "custom", service_ids=[self.service.id]
        )
        self.assertEqual(quote.total_minor, 16500)
        self.assertEqual(len(quote.snapshot["items"]), 4)
        self.assertIn("Synthetic colour grading", quote.snapshot["features"])

    def test_custom_estimate_rejects_missing_prices_unknown_fields_and_anonymous_access(self):
        payload = {
            "colour_grading": False,
            "quality_enhancement": True,
            "reel_duration": "30_50",
            "wants_wording": False,
            "wording_direction": "",
        }
        self.assertEqual(
            self.client.post(
                "/api/custom-estimate/", json.dumps(payload), content_type="application/json"
            ).status_code,
            401,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            "/api/custom-estimate/", json.dumps(payload), content_type="application/json"
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn("Quality enhancement", response.json()["error"])
        response = self.client.post(
            "/api/custom-estimate/",
            json.dumps({**payload, "total_minor": 1}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def enable_weighted_engine(self):
        CommercePolicy.objects.filter(pk=1).update(
            quotation_engine_enabled=True,
            quotation_point_minor=100,
            quotation_min_minor=5000,
            quotation_max_minor=50000,
        )
        self.policy.refresh_from_db()

    def test_weighted_engine_uses_approved_scores_and_returns_a_breakdown(self):
        self.enable_weighted_engine()
        selection = {
            "colour_grading": True,
            "quality_enhancement": True,
            "reel_duration": "20_30",
            "wants_wording": True,
            "wording_direction": "editor_choice",
            "song_choice": "suggest",
            "overlays": True,
            "beat_sync": True,
        }
        first = custom_estimate_result(selection)
        second = custom_estimate_result(selection)
        self.assertEqual(first["total_minor"], 12380)
        self.assertEqual(first["total_minor"], second["total_minor"])
        self.assertEqual(first["quotation"]["model"], "weighted_heuristic_v1")
        self.assertEqual(first["quotation"]["total_complexity_score"], "23.8")
        self.assertEqual(len(first["quotation"]["features"]), 7)
        self.assertEqual(sum(item["amount_minor"] for item in first["items"]), 12380)
        self.client.force_login(self.user)
        response = self.client.post(
            "/api/quote/", json.dumps(selection), content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total_minor"], 12380)
        self.assertEqual(response.json()["model"], "weighted_heuristic_v1")
        self.assertEqual(len(response.json()["breakdown"]), 8)

    def test_saved_weighted_snapshot_survives_later_pricing_changes(self):
        self.enable_weighted_engine()
        browser = self.client
        browser.force_login(self.user)
        response = browser.post(
            "/client/new-order/?new=1",
            {
                "title": "Weighted snapshot",
                "order_choice": "custom",
                "colour_grading": "on",
                "quality_enhancement": "on",
                "overlays": "on",
                "beat_sync": "on",
                "reel_duration": "20_30",
                "wants_wording": "on",
                "wording_direction": "editor_choice",
                "song_choice": "suggest",
            },
        )
        project = Project.objects.get(title="Weighted snapshot")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(project.quotation_snapshot["total_minor"], 12380)
        CommercePolicy.objects.filter(pk=1).update(quotation_point_minor=999)
        QuotationFeature.objects.filter(code="colour_grading").update(time_score=1)
        quote = create_quote(self.user, project.id, "custom")
        self.assertEqual(quote.total_minor, 12380)
        self.assertEqual(quote.snapshot["quotation"]["weights"]["time"], 40)
        self.assertEqual(quote.snapshot["quotation"]["inputs"]["overlays"], True)

    def test_admin_can_manage_weighted_policy_and_feature_scores(self):
        invalid_values = {
            field: getattr(self.policy, field) for field in PolicyForm.Meta.fields
        }
        invalid_values.update(
            {
                "quotation_engine_enabled": True,
                "quotation_time_weight": 50,
                "quotation_importance_weight": 20,
                "quotation_complexity_weight": 40,
                "quotation_point_minor": 100,
                "quotation_min_minor": 5000,
                "quotation_max_minor": 50000,
            }
        )
        invalid = PolicyForm(invalid_values, instance=self.policy, values_are_minor=True)
        self.assertFalse(invalid.is_valid())
        self.assertIn("must total 100%", invalid.errors["quotation_complexity_weight"][0])
        self.client.force_login(self.admin)
        pricing = self.client.get("/admin/pricing/")
        self.assertContains(pricing, "Weighted quotation engine")
        self.assertContains(pricing, "Beat sync")
        response = self.client.post(
            "/admin/pricing/quotation-features/beat_sync/",
            {
                "time_score": 5,
                "importance_score": 5,
                "complexity_score": 4,
                "multiplier": "1.250",
            },
        )
        self.assertRedirects(response, "/admin/pricing/")
        feature = QuotationFeature.objects.get(code="beat_sync")
        self.assertEqual(feature.complexity_score, 4)
        self.assertEqual(str(feature.multiplier), "1.250")

    def test_quote_and_accepted_terms_survive_catalog_edits(self):
        quote = self.quote()
        Plan.objects.filter(pk=self.plan.pk).update(price_minor=99999, name="Changed")
        CommercePolicy.objects.filter(pk=1).update(terms="Changed terms")
        order = accept_quote(self.user, self.project.id, quote.id)
        self.assertEqual(order.total_minor, 25000)
        self.assertEqual(order.terms_snapshot["items"][0]["name"], "Synthetic plan")
        self.assertEqual(order.terms_snapshot["terms"]["terms"], "TEST service terms")
        self.assertEqual(accept_quote(self.user, self.project.id, quote.id).id, order.id)

    def test_plan_period_price_is_server_calculated_and_snapshotted(self):
        Plan.objects.filter(pk=self.plan.pk).update(yearly_price_minor=None)
        with self.assertRaises(ValidationError):
            create_quote(
                self.user,
                self.project.id,
                "plan",
                self.plan.id,
                pricing_period=Plan.PricingPeriod.YEARLY,
            )

        quote = create_quote(
            self.user,
            self.project.id,
            "plan",
            self.plan.id,
            pricing_period=Plan.PricingPeriod.MONTHLY,
        )
        self.assertEqual(quote.total_minor, 200000)
        self.assertEqual(quote.snapshot["pricing_period"], Plan.PricingPeriod.MONTHLY)
        self.assertEqual(quote.snapshot["items"][0]["amount_minor"], 200000)

        Plan.objects.filter(pk=self.plan.pk).update(monthly_price_minor=999999)
        order = accept_quote(self.user, self.project.id, quote.id)
        self.assertEqual(order.total_minor, 200000)
        self.assertEqual(order.pricing_period, Plan.PricingPeriod.MONTHLY)

    def test_client_prices_and_privilege_changes_rejected(self):
        self.client.force_login(self.user)
        response = self.client.post(
            f"/client/projects/{self.project.id}/quote/",
            {"kind": "plan", "plan": self.plan.id, "scope_confirmed": "on", "total_minor": 1},
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(OrderQuote.objects.exists())
        self.assertEqual(self.client.post("/admin/pricing/plans/1/", {"price_minor": 1}).status_code, 403)

    def test_cross_client_quote_order_and_receipt_denied(self):
        payment = self.payment()
        apply_sandbox_event(*self.event(payment))
        self.client.force_login(self.other)
        for path in [
            f"/client/projects/{self.project.id}/quote/",
            f"/orders/{self.project.id}/",
            f"/payments/{payment.id}/receipt/",
        ]:
            self.assertEqual(self.client.get(path).status_code, 404)

    def test_financial_pages_are_not_cached(self):
        payment = self.payment()
        apply_sandbox_event(*self.event(payment))
        self.client.force_login(self.user)
        for path in [f"/orders/{self.project.id}/", f"/payments/{payment.id}/receipt/"]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Cache-Control"], "no-store, private")

    def test_incomplete_or_disabled_catalog_cannot_quote(self):
        Plan.objects.filter(pk=self.plan.pk).update(revision_limit=None)
        with self.assertRaises(ValidationError):
            self.quote()
        self.policy.quotes_enabled = False
        self.policy.save()
        with self.assertRaises(ValidationError):
            create_quote(self.user, self.project.id, "custom", service_ids=[self.service.id])

    def test_currency_mismatch_and_inactive_service_rejected(self):
        CustomService.objects.filter(pk=self.service.pk).update(currency="USD")
        with self.assertRaises(ValidationError):
            create_quote(self.user, self.project.id, "custom", service_ids=[self.service.id])
        CustomService.objects.filter(pk=self.service.pk).update(currency="INR", active=False)
        with self.assertRaises(ValidationError):
            create_quote(self.user, self.project.id, "custom", service_ids=[self.service.id])

    def test_old_quote_cannot_replace_newer_review(self):
        old = self.quote()
        self.quote()
        with self.assertRaises(ValidationError):
            accept_quote(self.user, self.project.id, old.id)

    def test_payment_attempt_is_idempotent_and_locks_quote(self):
        payment = self.payment()
        self.assertEqual(start_checkout(self.user, self.project.id).id, payment.id)
        self.assertEqual(Payment.objects.count(), 1)
        with self.assertRaises(ValidationError):
            self.quote()

    def test_invalid_signature_wrong_amount_currency_reference_and_order_rejected(self):
        payment = self.payment()
        with self.assertRaises(ValidationError):
            apply_sandbox_event(self.event(payment)[0], "invalid")
        for extra in [
            {"amount_minor": 1},
            {"currency": "USD"},
            {"reference": "wrong"},
            {"order_id": str(uuid.uuid4())},
            {"amount_minor": True},
        ]:
            with self.assertRaises(ValidationError):
                apply_sandbox_event(*self.event(payment, **extra))
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, "payment_pending")
        self.assertFalse(PaymentEvent.objects.exists())

    def test_failure_success_duplicate_and_late_failure(self):
        payment = self.payment()
        apply_sandbox_event(*self.event(payment, "failed"))
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, "payment_pending")
        self.assertIsNone(self.project.payment_completed_at)
        signed = self.event(payment)
        first = apply_sandbox_event(*signed)
        self.assertEqual(apply_sandbox_event(*signed).id, first.id)
        self.project.refresh_from_db()
        confirmed_at = self.project.payment_completed_at
        apply_sandbox_event(*self.event(payment, "failed"))
        apply_sandbox_event(*self.event(payment))
        self.project.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.project.payment_completed_at, confirmed_at)
        self.assertEqual(self.project.status, "payment_completed")
        self.assertEqual(self.order.payment_status, "confirmed")
        self.assertIsNone(self.project.expected_delivery_at)
        self.assertEqual(Project.objects.count(), 1)
        self.assertEqual(AuditLog.objects.filter(action="payment.confirmed").count(), 1)

    def test_paid_consultations_are_idempotent_and_admin_operated(self):
        self.project.call_before = True
        self.project.call_after = True
        self.project.save()
        payment = self.payment()
        self.assertFalse(CallRequest.objects.exists())
        signed = self.event(payment)
        apply_sandbox_event(*signed)
        apply_sandbox_event(*signed)
        apply_sandbox_event(*self.event(payment))
        self.assertEqual(CallRequest.objects.count(), 2)
        self.assertEqual(Notification.objects.filter(recipient=self.user, project=self.project).count(), 3)
        call = CallRequest.objects.get(stage="before")
        level = EditorProficiency.objects.get(level="beginner")
        consultant = User.objects.create_user(
            "consultant@example.test", "synthetic-password", role="editor", name="Consultant"
        )
        editor = Editor.objects.create(
            user=consultant, approved=True, proficiency=level, approved_by=self.admin
        )
        when = timezone.now() + timedelta(days=1)
        self.client.force_login(self.other)
        self.assertEqual(
            self.client.post(f"/admin/calls/{call.id}/action/", {"action": "complete"}).status_code, 403
        )
        self.assertEqual(self.client.get("/admin/calls/").status_code, 403)
        self.client.force_login(self.admin)
        self.assertContains(self.client.get("/admin/calls/"), "Commerce test")
        response = self.client.post(
            f"/admin/calls/{call.id}/action/",
            {"action": "schedule", "editor": str(editor.id), "scheduled_at": when.strftime("%Y-%m-%dT%H:%M")},
        )
        self.assertEqual(response.status_code, 302)
        call.refresh_from_db()
        self.assertEqual(call.status, "scheduled")
        self.assertEqual(call.editor_id, editor.id)
        self.client.force_login(consultant)
        self.assertContains(self.client.get("/orders/notifications/"), "consultation scheduled")
        self.assertContains(self.client.get("/editor/calls/"), "Commerce test")
        self.assertEqual(self.client.get(f"/editor/projects/{self.project.id}/").status_code, 404)
        self.client.force_login(self.admin)
        self.client.post(f"/admin/calls/{call.id}/action/", {"action": "complete"})
        call.refresh_from_db()
        self.assertEqual(call.status, "completed")
        self.assertEqual(AuditLog.objects.filter(action="call.completed", target_id=str(call.id)).count(), 1)

    def test_notification_inbox_scopes_null_and_project_events(self):
        private = Notification.objects.create(
            recipient=self.user, event_key="private-account", message="Account update"
        )
        alien = Notification.objects.create(
            recipient=self.other, event_key="alien-account", message="Other account"
        )
        self.client.force_login(self.user)
        self.assertContains(self.client.get("/orders/notifications/"), "Account update")
        self.assertNotContains(self.client.get("/orders/notifications/"), "Other account")
        self.assertEqual(self.client.post(f"/orders/notifications/{alien.id}/read/").status_code, 404)
        self.assertEqual(self.client.post(f"/orders/notifications/{private.id}/read/").status_code, 302)
        self.assertEqual(self.client.post(f"/orders/notifications/{private.id}/read/").status_code, 302)
        private.refresh_from_db()
        self.assertIsNotNone(private.read_at)
        self.assertEqual(
            AuditLog.objects.filter(action="notification.read", target_id=str(private.id)).count(), 1
        )

    def test_conflicting_event_id_rejected(self):
        payment = self.payment()
        apply_sandbox_event(*self.event(payment, event_id="same"))
        with self.assertRaises(ValidationError):
            apply_sandbox_event(*self.event(payment, "failed", event_id="same"))

    def test_browser_success_claim_never_confirms_payment(self):
        self.payment()
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(f"/orders/{self.project.id}/?success=true").status_code, 200)
        self.assertEqual(
            self.client.post(f"/orders/{self.project.id}/checkout/", {"status": "confirmed"}).status_code, 403
        )
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, "payment_pending")

    @override_settings(PAYMENT_MODE="disabled")
    def test_payments_disabled_by_default(self):
        accept_quote(self.user, self.project.id, self.quote().id)
        with self.assertRaises(ValidationError):
            start_checkout(self.user, self.project.id)
        self.assertEqual(
            self.client.post(
                "/api/payments/sandbox/webhook/", "{}", content_type="application/json"
            ).status_code,
            503,
        )

    @override_settings(DEBUG=False)
    def test_sandbox_cannot_activate_in_production(self):
        accept_quote(self.user, self.project.id, self.quote().id)
        with self.assertRaises(ValidationError):
            start_checkout(self.user, self.project.id)

    def test_admin_validation_empty_states_and_saved_plan(self):
        self.assertFalse(PlanForm({"name": "Incomplete", "active": True}, instance=Plan(slot=2)).is_valid())
        self.assertFalse(PolicyForm({"quotes_enabled": True}).is_valid())
        self.client.force_login(self.admin)
        self.assertContains(self.client.get("/admin/pricing/"), "Three plan slots")
        self.assertContains(self.client.get("/admin/orders/?payment=paid"), "No matching orders")
        data = {"name": "Draft second plan", "currency": "INR", "features": "Cuts\nCaptions"}
        self.assertEqual(self.client.post("/admin/pricing/plans/2/", data).status_code, 302)
        self.assertEqual(Plan.objects.get(slot=2).features, ["Cuts", "Captions"])

    def test_admin_enters_major_currency_amounts_and_legacy_values_round_trip(self):
        self.client.force_login(self.admin)
        legacy_page = self.client.get("/admin/pricing/plans/1/")
        self.assertContains(legacy_page, "Plan price (₹)")
        self.assertContains(legacy_page, 'value="250.00"', html=False)
        self.assertNotContains(legacy_page, "minor units")
        self.assertNotContains(legacy_page, "tokens")

        inr_form = PlanForm(
            {"name": "INR plan", "price_minor": "100.50", "currency": "INR"},
            instance=Plan(slot=2),
        )
        self.assertTrue(inr_form.is_valid(), inr_form.errors)
        inr_plan = inr_form.save()
        self.assertEqual(inr_plan.price_minor, 10050)
        rendered = PlanForm(instance=inr_plan).as_div()
        self.assertIn("Plan price (₹)", rendered)
        self.assertIn('value="100.50"', rendered)

        usd_form = PlanForm(
            {"name": "USD plan", "price_minor": "100.50", "currency": "USD"},
            instance=Plan(slot=3),
        )
        self.assertTrue(usd_form.is_valid(), usd_form.errors)
        self.assertEqual(usd_form.save().price_minor, 10050)

        jpy_form = PlanForm(
            {"name": "JPY plan", "price_minor": "100", "currency": "JPY"},
            instance=Plan(slot=2),
        )
        self.assertTrue(jpy_form.is_valid(), jpy_form.errors)
        jpy_plan = jpy_form.save(commit=False)
        self.assertEqual(jpy_plan.price_minor, 100)
        self.assertIn('value="100"', PlanForm(instance=jpy_plan).as_div())

    def test_admin_price_validation_respects_currency_precision(self):
        cases = [
            ("INR", "12.345", "INR supports up to 2 decimal places."),
            ("JPY", "12.5", "JPY does not support decimals."),
            ("USD", "not-a-number", "Enter a valid amount."),
            ("USD", "-1", "Enter zero or a positive amount."),
        ]
        for currency, amount, message in cases:
            with self.subTest(currency=currency, amount=amount):
                form = PlanForm(
                    {"name": "Invalid plan", "price_minor": amount, "currency": currency},
                    instance=Plan(slot=2),
                )
                self.assertFalse(form.is_valid())
                self.assertIn(message, form.errors["price_minor"])

    def test_money_display_uses_currency_symbols_and_exponents(self):
        self.assertEqual(format_money(10000, "INR"), "₹100.00")
        self.assertEqual(format_money(150000, "USD"), "$1,500.00")
        self.assertEqual(format_money(1500, "JPY"), "¥1,500")

    def test_admin_can_prepare_monthly_package_draft_without_publishing_it(self):
        self.assertFalse(
            PackageForm(
                {
                    "name": "Invalid draft",
                    "currency": "INR",
                    "video_allowance": 4,
                    "services": "Cuts",
                }
            ).is_valid()
        )
        self.client.force_login(self.admin)
        response = self.client.post(
            "/admin/pricing/packages/new/",
            {
                "name": "Creator four",
                "price_minor": "500.00",
                "currency": "INR",
                "video_allowance": 4,
                "revision_limit": 2,
                "priority": "on",
                "dedicated_editor": "on",
                "services": "Cuts\nCaptions",
            },
        )
        self.assertEqual(response.status_code, 302)
        package = InfluencerPackage.objects.get(name="Creator four")
        self.assertFalse(package.active)
        self.assertEqual(package.services, ["Cuts", "Captions"])
        self.assertContains(self.client.get("/admin/pricing/"), "Creator four")
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(f"/admin/pricing/packages/{package.id}/").status_code, 403)

    def test_full_quote_ui_and_receipt(self):
        self.client.force_login(self.user)
        response = self.client.post(
            f"/client/projects/{self.project.id}/quote/",
            {"kind": "custom", "services": [self.service.id], "scope_confirmed": "on"},
        )
        self.assertEqual(response.status_code, 302)
        review = self.client.get(response.url)
        self.assertContains(review, "₹115.00")
        accepted = self.client.post(response.url, {"csrfmiddlewaretoken": "test", "agree": "yes"})
        self.assertEqual(accepted.status_code, 302)
        self.client.post(f"/orders/{self.project.id}/checkout/")
        payment = Payment.objects.get()
        body, signature = self.event(payment)
        response = self.client.post(
            "/api/payments/sandbox/webhook/",
            body,
            content_type="application/json",
            HTTP_X_SANDBOX_SIGNATURE=signature,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(self.client.get(f"/payments/{payment.id}/receipt/"), "TEST RECEIPT")
