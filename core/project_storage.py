"""Remove an archived project's private objects, every stored version included."""

from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .models import File, Payment, Project, ProjectStorageCleanup
from .storage import delete_private_object_versions

DELETABLE_STATUSES = {Project.Status.COMPLETED, Project.Status.CANCELLED}
UNPAID_PROJECT_LIFETIME = timedelta(hours=36)
REMINDER_BEFORE_EXPIRY = timedelta(hours=6)
# A checkout started this recently may still be completing, so its project is left alone.
PAYMENT_IN_PROGRESS_GRACE = timedelta(hours=1)


def process_cleanup_job(job_pk):
    """Run one queued cleanup; return True when its objects are gone, False to retry later."""
    with transaction.atomic():
        job = ProjectStorageCleanup.objects.select_for_update().get(pk=job_pk)
        if job.state not in {ProjectStorageCleanup.State.PENDING, ProjectStorageCleanup.State.RETRY}:
            return job.state == ProjectStorageCleanup.State.COMPLETED
        job.state = ProjectStorageCleanup.State.PROCESSING
        job.attempts += 1
        job.last_attempt_at = timezone.now()
        job.save(update_fields=["state", "attempts", "last_attempt_at", "updated_at"])
    try:
        files = list(File.objects.filter(project_id=job.project_id).only("pk", "object_key"))
        for file in files:
            delete_private_object_versions(file.object_key)
    except Exception:
        ProjectStorageCleanup.objects.filter(pk=job.pk).update(
            state=ProjectStorageCleanup.State.RETRY,
            updated_at=timezone.now(),
        )
        return False
    now = timezone.now()
    with transaction.atomic():
        File.objects.filter(project_id=job.project_id).update(state="removed", updated_at=now)
        ProjectStorageCleanup.objects.filter(pk=job.pk).update(
            state=ProjectStorageCleanup.State.COMPLETED,
            object_count=len(files),
            completed_at=now,
            updated_at=now,
        )
    return True


def delete_project_files(project_id):
    """Archive a finished project and remove its stored files; return True when storage is clean."""
    with transaction.atomic():
        project = Project.objects.select_for_update().get(pk=project_id)
        if project.archived_at is None:
            if project.status not in DELETABLE_STATUSES:
                raise ValueError("Only completed or cancelled projects can be deleted.")
            project.archived_at = timezone.now()
            project.save(update_fields=["archived_at", "updated_at"])
        ProjectStorageCleanup.objects.get_or_create(project=project)
    return process_cleanup_job(project.pk)


def _unpaid_projects(now, older_than):
    recent_checkout = Payment.objects.filter(
        order__project_id__isnull=False, created_at__gte=now - PAYMENT_IN_PROGRESS_GRACE
    ).values("order__project_id")
    return (
        Project.objects.filter(
            status=Project.Status.PENDING,
            archived_at__isnull=True,
            created_at__lte=now - older_than,
        )
        .exclude(order__payment_status="confirmed")
        .exclude(pk__in=recent_checkout)
    )


def _reminders_sent():
    from operations.models import AuditLog

    return dict(
        AuditLog.objects.filter(action="project.expiry_reminder_sent").values_list("target_id", "created_at")
    )


def _send_expiry_reminder(project):
    user = project.client.user
    order = getattr(project, "order", None)
    amount = f"{order.total_minor / 100:,.2f} {order.currency}" if order and order.total_minor else "Not quoted yet"
    link = settings.PUBLIC_SITE_URL + reverse("order_summary", args=[project.pk])
    body = (
        f"Hello {user.name or 'there'},\n\n"
        "Your BRIO project is still waiting for payment and will be deleted in about 6 hours, "
        "together with every file you uploaded to it.\n\n"
        f"Project: {project.title}\n"
        f"Created: {timezone.localtime(project.created_at):%d %b %Y, %H:%M}\n"
        f"Amount due: {amount}\n"
        "Status: Payment pending\n\n"
        f"Complete your payment to keep it: {link}\n\n"
        "If you no longer need this project, you can ignore this email.\n\nTeam BRIO"
    )
    EmailMessage(
        f"Your BRIO project \"{project.title}\" expires in 6 hours",
        body,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
    ).send(fail_silently=False)


def _send_expired_email(project_id):
    project = Project.objects.select_related("client__user").get(pk=project_id)
    user = project.client.user
    if not (settings.NOTIFICATION_EMAIL_ENABLED and user.email):
        return False
    body = (
        f"Hello {user.name or 'there'},\n\n"
        f"Your BRIO project \"{project.title}\" was not paid within 36 hours, so it has been removed "
        "together with every file uploaded to it.\n\n"
        f"You can start a new project at any time: {settings.PUBLIC_SITE_URL}/client/new-order/\n\nTeam BRIO"
    )
    try:
        return EmailMessage(
            f"Your BRIO project \"{project.title}\" has expired", body, settings.DEFAULT_FROM_EMAIL, [user.email]
        ).send() == 1
    except Exception:
        return False


def schedule_unpaid_alarms(project):
    """Wake the site for the 30-hour reminder and, a few minutes after 36 hours, the removal."""
    from .qstash import schedule_sweep

    reminder_at = project.created_at + UNPAID_PROJECT_LIFETIME - REMINDER_BEFORE_EXPIRY + timedelta(minutes=1)
    schedule_sweep(reminder_at, f"unpaid-{project.pk}-reminder")
    schedule_sweep(project.created_at + UNPAID_PROJECT_LIFETIME + timedelta(minutes=5), f"unpaid-{project.pk}-expiry")


def send_expiry_reminders(now=None):
    """Email clients whose projects are 30 hours unpaid, once per project."""
    from .views import audit

    now = now or timezone.now()
    reminded = _reminders_sent()
    sent = 0
    for project in _unpaid_projects(now, UNPAID_PROJECT_LIFETIME - REMINDER_BEFORE_EXPIRY).select_related(
        "client__user", "order"
    ):
        if str(project.pk) in reminded:
            continue
        delivered = False
        if settings.NOTIFICATION_EMAIL_ENABLED and project.client.user.email:
            try:
                _send_expiry_reminder(project)
                delivered = True
            except Exception:
                delivered = False
        # Recorded even when email is off or fails, so expiry still follows six hours later.
        audit(None, "project.expiry_reminder_sent", project.pk, {"delivered": delivered})
        sent += delivered
    return sent


def expire_unpaid_projects(now=None):
    """Cancel, hide and remove the files of projects left unpaid 36 hours after creation.

    A project expires only once its reminder was recorded at least six hours earlier.
    """
    from .views import audit

    now = now or timezone.now()
    send_expiry_reminders(now)
    reminded = _reminders_sent()
    candidates = [
        project_id
        for project_id in _unpaid_projects(now, UNPAID_PROJECT_LIFETIME).values_list("pk", flat=True)
        if str(project_id) in reminded and reminded[str(project_id)] <= now - REMINDER_BEFORE_EXPIRY
    ]
    expired = 0
    for project_id in candidates:
        with transaction.atomic():
            cancelled = Project.objects.filter(
                pk=project_id, status=Project.Status.PENDING, archived_at__isnull=True
            ).update(status=Project.Status.CANCELLED, updated_at=now)
        if not cancelled:
            continue
        cleaned = delete_project_files(project_id)
        emailed = _send_expired_email(project_id)
        audit(None, "project.expired_unpaid", project_id, {"storage_cleared": cleaned, "emailed": emailed})
        expired += 1
    return expired
