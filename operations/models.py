from django.conf import settings
from django.db import models

from core.models import Project, Record


class EditorProficiency(models.Model):
    level = models.CharField(
        max_length=20,
        primary_key=True,
        choices=[("beginner", "Beginner"), ("intermediate", "Intermediate"), ("advanced", "Advanced")],
    )
    criteria = models.JSONField(default=dict)

    class Meta:
        db_table = "editor_proficiency"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(level__in=["beginner", "intermediate", "advanced"]),
                name="valid_proficiency",
            )
        ]


class Editor(Record):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="editor_profile"
    )
    phone = models.CharField(max_length=30)
    experience = models.TextField(max_length=5000)
    tools = models.CharField(max_length=500)
    portfolio = models.URLField(max_length=500)
    previous_work = models.TextField(max_length=5000)
    expertise = models.CharField(max_length=1000)
    other_information = models.TextField(blank=True, max_length=5000)
    approved = models.BooleanField(default=False)
    proficiency = models.ForeignKey(EditorProficiency, null=True, blank=True, on_delete=models.PROTECT)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="approved_editors",
    )
    workload_capacity = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        db_table = "editors"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(approved=False)
                | models.Q(proficiency__isnull=False, approved_by__isnull=False),
                name="approved_editor_has_review",
            )
        ]


class Admin(Record):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="admin_profile"
    )

    class Meta:
        db_table = "admins"


class EditorAvailability(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        BUSY = "busy", "Busy"
        OFFLINE = "offline", "Offline"
        LEAVE = "on_leave", "On leave"
        UNAVAILABLE = "temporarily_unavailable", "Temporarily unavailable"

    editor = models.OneToOneField(
        Editor, on_delete=models.PROTECT, related_name="availability", primary_key=True
    )
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.OFFLINE)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "editor_availability"


class ProjectComplexity(Record):
    project = models.OneToOneField(Project, on_delete=models.PROTECT)
    proficiency = models.ForeignKey(EditorProficiency, null=True, on_delete=models.PROTECT)
    rule_version = models.CharField(max_length=100, blank=True)
    internal_reason = models.TextField(blank=True)
    overridden_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)

    class Meta:
        db_table = "project_complexity"


class EditorAssignment(Record):
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="assignments")
    editor = models.ForeignKey(Editor, on_delete=models.PROTECT, related_name="assignments")
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    reason = models.TextField(blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "editor_assignments"
        constraints = [
            models.UniqueConstraint(
                fields=["project"], condition=models.Q(ended_at__isnull=True), name="one_current_assignment"
            )
        ]


class AssignmentQueue(Record):
    project = models.OneToOneField(Project, on_delete=models.PROTECT)
    proficiency = models.ForeignKey(EditorProficiency, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, default="waiting")

    class Meta:
        db_table = "assignment_queue"


class RoundRobinState(models.Model):
    proficiency = models.OneToOneField(EditorProficiency, on_delete=models.PROTECT, primary_key=True)
    last_editor = models.ForeignKey(Editor, null=True, blank=True, on_delete=models.PROTECT)
    sequence = models.PositiveBigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "round_robin_state"


class CallRequest(Record):
    project = models.ForeignKey(Project, on_delete=models.PROTECT)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    editor = models.ForeignKey(Editor, null=True, blank=True, on_delete=models.PROTECT)
    stage = models.CharField(max_length=20, choices=[("before", "Before editing"), ("after", "After draft")])
    scheduled_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, default="requested")

    class Meta:
        db_table = "call_requests"


class Notification(Record):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    project = models.ForeignKey(Project, null=True, blank=True, on_delete=models.PROTECT)
    event_key = models.CharField(max_length=200, unique=True)
    message = models.CharField(max_length=500)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notifications"


class EditorCoins(Record):
    editor = models.OneToOneField(Editor, on_delete=models.PROTECT, related_name="wallet")
    # Balance is derived from the ledger. No editable cached balance or invented conversion.
    earning_rule = models.JSONField(default=dict)

    class Meta:
        db_table = "editor_coins"


class RedemptionRequest(Record):
    wallet = models.ForeignKey(EditorCoins, on_delete=models.PROTECT, related_name="redemptions")
    amount = models.PositiveBigIntegerField()
    status = models.CharField(max_length=20, default="requested")
    payout_reference = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = "redemption_requests"


class CoinTransaction(Record):
    wallet = models.ForeignKey(EditorCoins, on_delete=models.PROTECT, related_name="transactions")
    project = models.ForeignKey(Project, null=True, blank=True, on_delete=models.PROTECT)
    redemption = models.ForeignKey(RedemptionRequest, null=True, blank=True, on_delete=models.PROTECT)
    event_key = models.CharField(max_length=200, unique=True)
    amount = models.BigIntegerField()
    kind = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("credit", "Credit"),
            ("reserve", "Reserved"),
            ("redeem", "Redeemed"),
            ("release", "Released"),
            ("adjustment", "Adjustment"),
        ],
    )
    rule_snapshot = models.JSONField(default=dict)

    class Meta:
        db_table = "coin_transactions"


class AuditLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    action = models.CharField(max_length=100)
    target_id = models.CharField(max_length=100)
    detail = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "audit_logs"
        ordering = ["-created_at"]
