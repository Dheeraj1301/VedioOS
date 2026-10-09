import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.functions import Lower


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError("Email is required.")
        user = self.model(email=email.strip().lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.update(role="admin", is_staff=True, is_superuser=True)
        return self.create_user(email, password, **extra)


class User(AbstractUser):
    class Role(models.TextChoices):
        CLIENT = "client", "Client"
        EDITOR = "editor", "Editor"
        ADMIN = "admin", "Admin"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=120)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.CLIENT)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    supabase_auth_user_id = models.UUIDField(null=True, blank=True, unique=True)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]
    objects = UserManager()

    class Meta:
        db_table = "users"
        constraints = [
            models.UniqueConstraint(Lower("email"), name="unique_email_case_insensitive"),
            models.CheckConstraint(
                condition=models.Q(role__in=["client", "editor", "admin"]), name="valid_user_role"
            ),
        ]

    def __str__(self):
        return self.email


class EmailVerificationChallenge(models.Model):
    """A short-lived, server-side challenge for activating a client account."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="email_verification_challenge",
    )
    code_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    sent_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "email_verification_challenges"



class Record(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Client(Record):
    user = models.OneToOneField(User, on_delete=models.PROTECT, related_name="client_profile")

    class Meta:
        db_table = "clients"


class Plan(Record):
    class PricingPeriod(models.TextChoices):
        PER_REEL = "per_reel", "Per Reel"
        MONTHLY = "monthly", "Monthly"
        YEARLY = "yearly", "Yearly"

    slot = models.PositiveSmallIntegerField(unique=True)
    name = models.CharField(max_length=100)
    price_minor = models.PositiveBigIntegerField(null=True, blank=True)
    monthly_price_minor = models.PositiveBigIntegerField(null=True, blank=True)
    yearly_price_minor = models.PositiveBigIntegerField(null=True, blank=True)
    currency = models.CharField(max_length=3, blank=True)
    features = models.JSONField(default=list)
    revision_limit = models.PositiveIntegerField(null=True, blank=True)
    delivery_hours = models.PositiveIntegerField(null=True, blank=True)
    duration_limit_seconds = models.PositiveIntegerField(null=True, blank=True)
    priority = models.PositiveSmallIntegerField(null=True, blank=True)
    active = models.BooleanField(default=False)

    class Meta:
        db_table = "plans"
        constraints = [
            models.CheckConstraint(condition=models.Q(slot__gte=1, slot__lte=3), name="three_plan_slots")
        ]

    def price_for_period(self, pricing_period):
        field = {
            self.PricingPeriod.PER_REEL: "price_minor",
            self.PricingPeriod.MONTHLY: "monthly_price_minor",
            self.PricingPeriod.YEARLY: "yearly_price_minor",
        }.get(pricing_period)
        return getattr(self, field) if field else None


class CustomService(Record):
    class Code(models.TextChoices):
        COLOUR_GRADING = "colour_grading", "Colour grading"
        QUALITY_ENHANCEMENT = "quality_enhancement", "Quality enhancement"
        DURATION_20_30 = "duration_20_30", "Duration: 20–30 seconds"
        DURATION_30_50 = "duration_30_50", "Duration: 30–50 seconds"
        DURATION_60_PLUS = "duration_60_plus", "Duration: 60+ seconds"
        DURATION_120_PLUS = "duration_120_plus", "Duration: 2 minutes+"
        WORDING = "wording", "Wording / on-screen text"

    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=32, choices=Code.choices, unique=True, null=True, blank=True)
    price_minor = models.PositiveBigIntegerField(null=True, blank=True)
    currency = models.CharField(max_length=3, blank=True)
    active = models.BooleanField(default=False)

    class Meta:
        db_table = "custom_services"


class Project(Record):
    class ReelDuration(models.TextChoices):
        SHORT = "20_30", "20–30 seconds"
        MEDIUM = "30_50", "30–50 seconds"
        LONG = "60_plus", "60+ seconds"
        EXTENDED = "120_plus", "2 minutes+"

    class WordingDirection(models.TextChoices):
        OWN_FONT = "own_font", "I have my own font"
        FONT_INSPO = "font_inspiration", "I will upload font inspiration"
        MATCH_REFERENCE = "match_reference", "Same as the reference"
        EDITOR_CHOICE = "editor_choice", "Editor’s choice"

    class Status(models.TextChoices):
        PENDING = "payment_pending", "Payment pending"
        PAID = "payment_completed", "Payment completed"
        WAITING = "awaiting_assignment", "Awaiting editor assignment"
        ASSIGNED = "editor_assigned", "Editor assigned"
        EDITING = "editing", "Editing in progress"
        DRAFT = "draft_uploaded", "Draft uploaded"
        REVIEW = "awaiting_review", "Awaiting client review"
        REVISION_REQUESTED = "revision_requested", "Revision requested"
        REVISING = "revision_in_progress", "Revision in progress"
        FINAL = "final_uploaded", "Final video uploaded"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="projects")
    title = models.CharField(max_length=160)
    requirements = models.TextField(blank=True, max_length=10000)
    selected_services = models.JSONField(default=list)
    colour_grading = models.BooleanField(default=False)
    quality_enhancement = models.BooleanField(default=False)
    overlays = models.BooleanField(default=False)
    beat_sync = models.BooleanField(default=False)
    reel_duration = models.CharField(max_length=20, choices=ReelDuration.choices, blank=True)
    wants_wording = models.BooleanField(default=False)
    wording_direction = models.CharField(
        max_length=24, choices=WordingDirection.choices, blank=True
    )
    font_name = models.CharField(max_length=120, blank=True)
    reference_notes = models.TextField(blank=True, max_length=5000)
    song_choice = models.CharField(
        max_length=20,
        choices=[
            ("provide", "I will provide my own song"),
            ("suggest", "Suggest a song for me"),
            ("both", "I will provide my own song and would also like editor's suggestion"),
        ],
        default="suggest",
    )
    song_information = models.TextField(blank=True, max_length=2000)
    call_before = models.BooleanField(default=False)
    call_after = models.BooleanField(default=False)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.PENDING)
    payment_completed_at = models.DateTimeField(null=True, blank=True)
    expected_delivery_at = models.DateTimeField(null=True, blank=True)
    quotation_snapshot = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "projects"
        ordering = ["-created_at"]


class Order(Record):
    project = models.OneToOneField(Project, on_delete=models.PROTECT, related_name="order")
    plan = models.ForeignKey(Plan, null=True, blank=True, on_delete=models.PROTECT)
    kind = models.CharField(max_length=12, choices=[("plan", "Plan"), ("custom", "Custom")], default="custom")
    pricing_period = models.CharField(
        max_length=12,
        choices=Plan.PricingPeriod.choices,
        default=Plan.PricingPeriod.PER_REEL,
    )
    terms_snapshot = models.JSONField(default=dict)
    total_minor = models.PositiveBigIntegerField(null=True, blank=True)
    currency = models.CharField(max_length=3, blank=True)
    payment_status = models.CharField(
        max_length=20,
        default="pending",
        choices=[
            ("pending", "Pending"),
            ("confirmed", "Confirmed"),
            ("failed", "Failed"),
            ("refunded", "Refunded"),
        ],
    )

    class Meta:
        db_table = "orders"


class Payment(Record):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="payments")
    provider = models.CharField(max_length=60)
    provider_reference = models.CharField(max_length=200)
    amount_minor = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3)
    status = models.CharField(max_length=20, default="pending")
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "payments"
        constraints = [
            models.UniqueConstraint(fields=["provider", "provider_reference"], name="unique_provider_payment")
        ]


class File(Record):
    class Category(models.TextChoices):
        SOURCE = "source", "Source video"
        IMAGE = "image", "Image"
        AUDIO = "audio", "Audio"
        REFERENCE = "reference", "Reference"
        FONT_REFERENCE = "font_reference", "Font inspiration"
        ASSET = "asset", "Other asset"
        DRAFT = "draft", "Edited draft"
        FINAL = "final", "Final video"

    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="files")
    uploader = models.ForeignKey(User, on_delete=models.PROTECT)
    filename = models.CharField(max_length=240)
    object_key = models.CharField(max_length=300, unique=True)
    storage_version = models.CharField(max_length=200, blank=True)
    content_type = models.CharField(max_length=100)
    size_bytes = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64)
    category = models.CharField(max_length=20, choices=Category.choices)
    state = models.CharField(
        max_length=12,
        choices=[("pending", "Pending"), ("ready", "Ready"), ("rejected", "Rejected")],
        default="pending",
    )
    expires_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    original = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="derivatives"
    )

    class Meta:
        db_table = "files"
        ordering = ["created_at"]


class ProjectVersion(Record):
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="versions")
    file = models.OneToOneField(File, on_delete=models.PROTECT)
    number = models.PositiveIntegerField()
    note = models.TextField(blank=True)
    is_final = models.BooleanField(default=False)
    accepted_at = models.DateTimeField(null=True, blank=True)
    assignment = models.ForeignKey(
        "operations.EditorAssignment", null=True, blank=True, on_delete=models.PROTECT
    )

    class Meta:
        db_table = "project_versions"
        constraints = [models.UniqueConstraint(fields=["project", "number"], name="unique_project_version")]


class RevisionRequest(Record):
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="revisions")
    version = models.ForeignKey(ProjectVersion, on_delete=models.PROTECT)
    requested_by = models.ForeignKey(User, on_delete=models.PROTECT)
    instructions = models.TextField()
    status = models.CharField(max_length=20, default="requested")

    class Meta:
        db_table = "revision_requests"


class InfluencerPackage(Record):
    name = models.CharField(max_length=100)
    price_minor = models.PositiveBigIntegerField(null=True, blank=True)
    currency = models.CharField(max_length=3, blank=True)
    video_allowance = models.PositiveIntegerField(null=True, blank=True)
    revision_limit = models.PositiveIntegerField(null=True, blank=True)
    priority = models.BooleanField(default=False)
    dedicated_editor = models.BooleanField(default=False)
    services = models.JSONField(default=list)
    active = models.BooleanField(default=False)

    class Meta:
        db_table = "influencer_packages"


class Subscription(Record):
    client = models.ForeignKey(Client, on_delete=models.PROTECT)
    package = models.ForeignKey(InfluencerPackage, on_delete=models.PROTECT)
    terms_snapshot = models.JSONField(default=dict)
    status = models.CharField(max_length=20, default="pending")
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "subscriptions"


class UploadPolicy(models.Model):
    """Technical local limits are seeded explicitly, never sold as plan terms."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    max_bytes = models.PositiveBigIntegerField()
    allowed_types = models.JSONField(default=dict)
    enabled = models.BooleanField(default=True)

    class Meta:
        db_table = "upload_policy"


class AuthAttempt(models.Model):
    key = models.CharField(max_length=64, unique=True)
    failures = models.PositiveIntegerField(default=0)
    window_started = models.DateTimeField()

    class Meta:
        db_table = "auth_attempts"


class CommercePolicy(models.Model):
    """Unconfigured by default; prices and commercial promises require owner input."""

    class PricingContext(models.TextChoices):
        UNCONFIGURED = "unconfigured", "Unconfigured"
        TEST = "test", "Test only"
        PRODUCTION = "production", "Production"

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    pricing_context = models.CharField(
        max_length=20,
        choices=PricingContext.choices,
        default=PricingContext.UNCONFIGURED,
    )
    currency = models.CharField(max_length=3, blank=True)
    custom_base_minor = models.PositiveBigIntegerField(null=True, blank=True)
    custom_revision_limit = models.PositiveIntegerField(null=True, blank=True)
    custom_delivery_hours = models.PositiveIntegerField(null=True, blank=True)
    custom_duration_limit_seconds = models.PositiveIntegerField(null=True, blank=True)
    custom_priority = models.PositiveSmallIntegerField(null=True, blank=True)
    quotation_engine_enabled = models.BooleanField(default=False)
    quotation_time_weight = models.PositiveSmallIntegerField(default=40)
    quotation_importance_weight = models.PositiveSmallIntegerField(default=20)
    quotation_complexity_weight = models.PositiveSmallIntegerField(default=40)
    quotation_point_minor = models.PositiveBigIntegerField(null=True, blank=True)
    quotation_min_minor = models.PositiveBigIntegerField(null=True, blank=True)
    quotation_max_minor = models.PositiveBigIntegerField(null=True, blank=True)
    terms = models.TextField(blank=True, max_length=12000)
    delivery_terms = models.TextField(blank=True, max_length=4000)
    refund_terms = models.TextField(blank=True, max_length=4000)
    tax_terms = models.TextField(blank=True, max_length=4000)
    quotes_enabled = models.BooleanField(default=False)
    review_rule = models.CharField(
        max_length=40,
        blank=True,
        choices=[("latest_request_v1", "One revision per request; review and accept latest submission")],
        help_text="Owner-approved rule for new quotes only. Blank disables review actions. Excess revisions require a separate agreement; acceptance is final.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "commerce_policy"
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name="one_commerce_policy")]


class QuotationFeature(models.Model):
    class Code(models.TextChoices):
        COLOUR_GRADING = "colour_grading", "Colour grading"
        QUALITY_ENHANCEMENT = "quality_enhancement", "Quality enhancement"
        DURATION = "duration", "Reel duration"
        FONT_OPTION = "font_option", "Font option"
        SONG_OPTION = "song_option", "Song option"
        OVERLAYS = "overlays", "Overlays"
        BEAT_SYNC = "beat_sync", "Beat sync"

    code = models.CharField(max_length=32, choices=Code.choices, unique=True)
    time_score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    importance_score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    complexity_score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    multiplier = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        default=1,
        validators=[MinValueValidator(0.001), MaxValueValidator(100)],
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "quotation_features"
        ordering = ["code"]


class OrderQuote(Record):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="quotes")
    snapshot = models.JSONField()
    total_minor = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3)
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "order_quotes"
        ordering = ["-created_at"]


class PaymentEvent(Record):
    provider = models.CharField(max_length=60)
    event_id = models.CharField(max_length=200)
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="events")
    payload_digest = models.CharField(max_length=64)
    outcome = models.CharField(max_length=20)

    class Meta:
        db_table = "payment_events"
        constraints = [models.UniqueConstraint(fields=["provider", "event_id"], name="unique_payment_event")]


class DeliveryAcceptance(Record):
    project = models.OneToOneField(Project, on_delete=models.PROTECT, related_name="acceptance")
    version = models.OneToOneField(ProjectVersion, on_delete=models.PROTECT)
    accepted_by = models.ForeignKey(User, on_delete=models.PROTECT)
    assignment = models.ForeignKey("operations.EditorAssignment", on_delete=models.PROTECT)
    terms_snapshot = models.JSONField(default=dict)
    earning_status = models.CharField(max_length=30, default="pending_policy")

    class Meta:
        db_table = "delivery_acceptances"
