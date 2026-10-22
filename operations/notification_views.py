from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from core.models import Order, User
from core.permissions import role_required, visible_projects
from core.views import audit

from .models import Notification, NotificationCampaign, NotificationDelivery
from .notification_forms import NotificationCampaignForm
from .support import support_request_for


def visible_notice(user, notice_id):
    return get_object_or_404(
        Notification.objects.select_related("campaign", "campaign__created_by", "project")
        .filter(recipient=user)
        .filter(Q(campaign__isnull=True) | Q(campaign__status=NotificationCampaign.Status.PUBLISHED))
        .filter(Q(project__isnull=True) | Q(project__in=visible_projects(user))),
        pk=notice_id,
    )


def notification_destination(user, notice):
    if notice.campaign_id:
        return None
    if notice.reference_type == Notification.ReferenceType.SUPPORT_TICKET and notice.reference_id:
        support_request = support_request_for(user, notice.reference_id)
        return reverse("support_detail", kwargs={"request_id": support_request.pk})
    if (
        user.role == "admin"
        and notice.reference_type == Notification.ReferenceType.ORDER
        and notice.reference_id
    ):
        order = get_object_or_404(
            Order.objects.filter(project__in=visible_projects(user)), pk=notice.reference_id
        )
        return reverse("admin_order_detail", kwargs={"order_id": order.pk})
    if notice.project_id:
        route = {
            "admin": "admin_project",
            "client": "client_project_communication",
            "editor": "editor_project_communication",
        }[user.role]
        return reverse(route, kwargs={"project_id": notice.project_id})
    return None


@require_GET
@role_required("client", "editor", "admin")
def notification_detail(request, notice_id):
    with transaction.atomic():
        notice = visible_notice(request.user, notice_id)
        if notice.read_at is None:
            notice.read_at = timezone.now()
            notice.save(update_fields=["read_at", "updated_at"])
            audit(
                request.user,
                "notification.read",
                notice.pk,
                {
                    "campaign": str(notice.campaign_id) if notice.campaign_id else None,
                    "reference_type": notice.reference_type,
                    "reference_id": str(notice.reference_id) if notice.reference_id else None,
                },
            )
    destination = notification_destination(request.user, notice)
    if destination:
        return redirect(destination)
    return render(
        request,
        "notification_detail.html",
        {"title": notice.campaign.title if notice.campaign else "Notification", "notice": notice},
    )


@require_POST
@role_required("client", "editor", "admin")
def mark_all_notifications_read(request):
    now = timezone.now()
    notices = Notification.objects.filter(recipient=request.user, read_at__isnull=True).filter(
        Q(project__isnull=True) | Q(project__in=visible_projects(request.user))
    )
    ids = list(notices.values_list("id", flat=True))
    notices.update(read_at=now, updated_at=now)
    for notice_id in ids:
        audit(request.user, "notification.read", notice_id, {"source": "mark_all"})
    next_path = request.POST.get("next", "")
    return redirect(
        next_path if next_path.startswith("/") and not next_path.startswith("//") else "notifications"
    )


@require_GET
@role_required("client", "editor", "admin")
def notification_poster(request, campaign_id):
    campaign = get_object_or_404(NotificationCampaign, pk=campaign_id, poster__isnull=False)
    if (
        request.user.role != "admin"
        and not Notification.objects.filter(campaign=campaign, recipient=request.user).exists()
    ):
        raise Http404
    response = HttpResponse(bytes(campaign.poster), content_type=campaign.poster_content_type)
    response["Cache-Control"] = "private, max-age=300"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@require_GET
@role_required("admin")
def admin_notifications(request):
    campaigns = NotificationCampaign.objects.select_related("created_by", "target_user").annotate(
        recipient_count=Count("notifications"),
        read_count=Count("notifications", filter=Q(notifications__read_at__isnull=False)),
    )
    return render(
        request, "operations/notifications.html", {"title": "Notifications", "campaigns": campaigns}
    )


@role_required("admin")
def admin_notification_form(request, campaign_id=None):
    campaign = get_object_or_404(NotificationCampaign, pk=campaign_id) if campaign_id else None
    if campaign and campaign.status != NotificationCampaign.Status.DRAFT:
        messages.error(request, "Published or archived notifications cannot be edited. Unpublish it first.")
        return redirect("admin_notifications")
    form = NotificationCampaignForm(request.POST or None, request.FILES or None, instance=campaign)
    if request.method == "POST" and form.is_valid():
        saved = form.save(commit=False)
        if campaign is None:
            saved.created_by = request.user
        saved.save()
        audit(request.user, "notification.campaign_saved", saved.pk, {"audience": saved.audience})
        messages.success(request, "Notification draft saved.")
        return redirect("admin_notifications")
    return render(
        request,
        "operations/notification_form.html",
        {
            "title": "Edit notification" if campaign else "Create notification",
            "form": form,
            "campaign": campaign,
        },
    )


def _recipients(campaign):
    users = User.objects.filter(is_active=True)
    if campaign.audience == NotificationCampaign.Audience.CLIENTS:
        return users.filter(role="client")
    if campaign.audience == NotificationCampaign.Audience.EDITORS:
        return users.filter(role="editor")
    if campaign.audience == NotificationCampaign.Audience.USER:
        return users.filter(pk=campaign.target_user_id)
    return users


@require_POST
@role_required("admin")
def admin_notification_action(request, campaign_id):
    action = request.POST.get("action")
    with transaction.atomic():
        campaign = get_object_or_404(NotificationCampaign.objects.select_for_update(), pk=campaign_id)
        if action == "publish" and campaign.status != NotificationCampaign.Status.PUBLISHED:
            campaign.status = NotificationCampaign.Status.PUBLISHED
            campaign.published_at = timezone.now()
            campaign.save(update_fields=["status", "published_at", "updated_at"])
            for user in _recipients(campaign).iterator():
                Notification.objects.get_or_create(
                    recipient=user,
                    campaign=campaign,
                    event_key=f"campaign:{campaign.pk}:user:{user.pk}",
                    defaults={"message": campaign.body[:500]},
                )
        elif action == "unpublish" and campaign.status == NotificationCampaign.Status.PUBLISHED:
            campaign.status = NotificationCampaign.Status.DRAFT
            campaign.published_at = None
            campaign.save(update_fields=["status", "published_at", "updated_at"])
        elif action == "archive":
            campaign.status = NotificationCampaign.Status.ARCHIVED
            campaign.save(update_fields=["status", "updated_at"])
        elif action == "delete" and campaign.status == NotificationCampaign.Status.DRAFT:
            notice_ids = campaign.notifications.values_list("id", flat=True)
            NotificationDelivery.objects.filter(notification_id__in=notice_ids).delete()
            campaign.notifications.all().delete()
            campaign.delete()
            messages.success(request, "Notification deleted.")
            return redirect("admin_notifications")
        else:
            raise Http404
        audit(request.user, f"notification.{action}", campaign.pk, {})
    messages.success(request, f"Notification {action}d.")
    return redirect("admin_notifications")
