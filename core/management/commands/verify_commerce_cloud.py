"""Check commerce against PostgreSQL; every fixture/change is rolled back."""

import hashlib
import hmac
import json
import secrets
import time
import uuid

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.test import override_settings

from core.commerce import accept_quote, create_quote
from core.models import Client, CommercePolicy, CustomService, Order, PaymentEvent, Project, User
from core.payments import apply_sandbox_event, start_checkout


class Command(BaseCommand):
    help = "Verify quotes, payment matching and duplicate events on PostgreSQL without retaining test data."

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            raise CommandError("This check requires PostgreSQL.")
        marker = uuid.uuid4().hex
        secret = secrets.token_urlsafe(40)
        with (
            transaction.atomic(),
            override_settings(DEBUG=True, PAYMENT_MODE="sandbox", SANDBOX_PAYMENT_SECRET=secret),
        ):
            user = User.objects.create_user(
                f"commerce-check-{marker}@example.test", name="Temporary commerce check"
            )
            project = Project.objects.create(
                client=Client.objects.create(user=user), title="Temporary commerce check"
            )
            order = Order.objects.create(project=project)
            CommercePolicy.objects.update_or_create(
                pk=1,
                defaults={
                    "currency": "INR",
                    "custom_base_minor": 10000,
                    "custom_revision_limit": 2,
                    "custom_delivery_hours": 24,
                    "custom_duration_limit_seconds": 60,
                    "custom_priority": 1,
                    "terms": "Temporary test only",
                    "delivery_terms": "Temporary test only",
                    "refund_terms": "Temporary test only",
                    "tax_terms": "Temporary test only",
                    "quotes_enabled": True,
                },
            )
            service = CustomService.objects.create(
                name=f"Test {marker}", price_minor=1500, currency="INR", active=True
            )
            quote = create_quote(user, project.id, "custom", service_ids=[service.id])
            if quote.total_minor != 11500:
                raise CommandError("Server quote total failed.")
            accept_quote(user, project.id, quote.id)
            payment = start_checkout(user, project.id)
            if start_checkout(user, project.id).id != payment.id:
                raise CommandError("Checkout idempotency failed.")
            payload = {
                "event_id": marker,
                "reference": payment.provider_reference,
                "order_id": str(order.id),
                "amount_minor": 11500,
                "currency": "INR",
                "status": "confirmed",
            }
            body = json.dumps(payload).encode()
            stamp = str(int(time.time()))
            signature = (
                stamp
                + "."
                + hmac.new(secret.encode(), stamp.encode() + b"." + body, hashlib.sha256).hexdigest()
            )
            first = apply_sandbox_event(body, signature)
            second = apply_sandbox_event(body, signature)
            project.refresh_from_db()
            if (
                first.id != second.id
                or project.status != "payment_completed"
                or PaymentEvent.objects.filter(payment=payment).count() != 1
            ):
                raise CommandError("Payment activation/idempotency failed.")
            transaction.set_rollback(True)
        if User.objects.filter(email=f"commerce-check-{marker}@example.test").exists():
            raise CommandError("Rollback verification failed.")
        self.stdout.write(
            self.style.SUCCESS(
                "PASS: PostgreSQL quote, accepted snapshot, payment, duplicate event and rollback. No test data retained."
            )
        )
