"""Synthetic fixtures shared by isolated tests and explicitly scoped cloud verification."""

import uuid

from django.utils import timezone

from core.models import Client, Order, Payment, Project, User
from operations.models import AssignmentPolicy, Editor, EditorAvailability

POLICY_VALUES = {
    "manual_enabled": True,
    "automatic_enabled": True,
    "busy_strategy": "skip",
    "manual_pointer": "preserve",
    "matching": "exact",
    "capacity_scope": "open_assignments",
    "roster_order": "joined",
    "queue_order": "paid_at",
}


def create_people(prefix=None, password=None):
    prefix = prefix or uuid.uuid4().hex
    admin = User.objects.create_user(
        f"assignment-admin-{prefix}@example.test", password, name="Synthetic manager", role="admin"
    )
    buyer = User.objects.create_user(
        f"assignment-client-{prefix}@example.test", password, name="Synthetic client"
    )
    client = Client.objects.create(user=buyer)
    editors = []
    for index in range(3):
        user = User.objects.create_user(
            f"assignment-editor{index}-{prefix}@example.test",
            password,
            name=f"Editor {index + 1}",
            role="editor",
        )
        editor = Editor.objects.create(
            user=user, approved=True, approved_by=admin, proficiency_id="beginner", workload_capacity=1
        )
        EditorAvailability.objects.create(editor=editor, status="available")
        editors.append(editor)
    return admin, client, editors


def paid_project(client, title="Synthetic assignment", paid=True):
    project = Project.objects.create(
        client=client,
        title=title,
        status="payment_completed" if paid else "payment_pending",
        payment_completed_at=timezone.now() if paid else None,
    )
    order = Order.objects.create(
        project=project, total_minor=10000, currency="INR", payment_status="confirmed" if paid else "pending"
    )
    if paid:
        Payment.objects.create(
            order=order,
            provider="sandbox",
            provider_reference=uuid.uuid4().hex,
            amount_minor=10000,
            currency="INR",
            status="confirmed",
            confirmed_at=timezone.now(),
        )
    return project


def enable_test_policy():
    return AssignmentPolicy.objects.update_or_create(pk=1, defaults=POLICY_VALUES)[0]
