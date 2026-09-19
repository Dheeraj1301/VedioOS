import base64
import hashlib
import json
import re
import uuid
from datetime import timedelta
from pathlib import PurePath

from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .forms import LoginForm, ProjectForm, RegistrationForm
from .models import AuthAttempt, Client, File, Order, Payment, Plan, UploadPolicy
from .permissions import can_upload, project_for, role_required, visible_files, visible_projects
from .storage import download_permission, inspect_object, upload_permission


def audit(user, action, target, detail=None):
    from operations.models import AuditLog

    AuditLog.objects.create(actor=user, action=action, target_id=str(target), detail=detail or {})


def auth_rate_limited(request):
    """DB-backed local limiter; no proxy headers are trusted as client identity."""
    key = hashlib.sha256(request.META.get("REMOTE_ADDR", "unknown").encode()).hexdigest()
    attempt, _ = AuthAttempt.objects.get_or_create(key=key, defaults={"window_started": timezone.now()})
    if attempt.window_started < timezone.now() - timedelta(minutes=15):
        AuthAttempt.objects.filter(pk=attempt.pk).update(failures=0, window_started=timezone.now())
        attempt.failures = 0
    if attempt.failures >= 30:
        return True
    AuthAttempt.objects.filter(pk=attempt.pk).update(failures=F("failures") + 1)
    return False


def landing(request):
    return render(request, "landing.html", {"plans": Plan.objects.filter(active=True)})


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    if request.method == "POST" and auth_rate_limited(request):
        return render(
            request,
            "error.html",
            {"message": "Too many attempts. Please try again in 15 minutes."},
            status=429,
        )
    form = RegistrationForm(request.POST or None)
    if request.method == "POST":
        if any(
            key in request.POST for key in ["role", "is_staff", "is_superuser", "approved", "proficiency"]
        ):
            raise PermissionDenied("Account permissions cannot be set during registration.")
        if form.is_valid():
            try:
                with transaction.atomic():
                    user = form.save(commit=False)
                    user.role = "client"
                    user.save()
                    Client.objects.create(user=user)
                    audit(user, "client.registered", user.pk)
                login(request, user)
                return redirect("client_dashboard")
            except IntegrityError:
                form.add_error("email", "This account could not be created. Try logging in.")
    return render(
        request,
        "auth.html",
        {
            "form": form,
            "title": "Make room for your next idea.",
            "subtitle": "Create your client account. Your footage stays private.",
            "button": "Create account",
            "mode": "register",
        },
    )


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    if request.method == "POST" and auth_rate_limited(request):
        return render(
            request,
            "error.html",
            {"message": "Too many attempts. Please try again in 15 minutes."},
            status=429,
        )
    form = LoginForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        return redirect("dashboard")
    return render(
        request,
        "auth.html",
        {
            "form": form,
            "title": "Back to your next great edit.",
            "subtitle": "Sign in to your VedioOS workspace.",
            "button": "Log in",
            "mode": "login",
        },
    )


@require_POST
def logout_view(request):
    logout(request)
    return redirect("landing")


@role_required("client", "editor", "admin")
def dashboard(request):
    return redirect(
        {"client": "client_dashboard", "editor": "editor_dashboard", "admin": "admin_dashboard"}[
            request.user.role
        ]
    )


@role_required("client")
def client_dashboard(request):
    projects = visible_projects(request.user)
    return render(
        request,
        "client/dashboard.html",
        {
            "projects": projects[:5],
            "project_count": projects.count(),
            "completed_count": projects.filter(status="completed").count(),
            "title": "Your creative workspace",
        },
    )


@role_required("client")
def new_order(request):
    form = ProjectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            project = form.save(commit=False)
            project.client = request.user.client_profile
            project.save()
            Order.objects.create(project=project)
            audit(request.user, "project.draft_created", project.pk)
        messages.success(request, "Project saved. Add your original files below.")
        return redirect("client_project", project_id=project.pk)
    return render(request, "client/new_order.html", {"form": form, "title": "Start a new edit"})


@role_required("client")
def my_projects(request):
    return render(
        request, "projects.html", {"projects": visible_projects(request.user), "title": "My projects"}
    )


@role_required("client", "editor", "admin")
def project_detail(request, project_id, area):
    if request.user.role != area:
        raise PermissionDenied
    project = project_for(request.user, project_id)
    policy = UploadPolicy.objects.filter(pk=1, enabled=True).first()
    categories = (
        [
            ("source", "Source video"),
            ("image", "Images"),
            ("audio", "Audio"),
            ("reference", "Inspiration / reference"),
            ("asset", "Other asset"),
        ]
        if area == "client"
        else [("draft", "Edited draft"), ("final", "Final video")]
    )
    allowed = [(key, label) for key, label in categories if can_upload(request.user, project, key)]
    from operations.messages import message_page

    project_messages, older_cursor = message_page(request.user, project, request.GET.get("messages_before"))

    return render(
        request,
        "project_detail.html",
        {
            "project": project,
            "calls": project.callrequest_set.select_related("editor__user").order_by("stage"),
            "project_messages": project_messages,
            "older_message_cursor": older_cursor,
            "is_older_message_page": bool(request.GET.get("messages_before")),
            "message_request_key": uuid.uuid4(),
            "title": project.title,
            "files": visible_files(request.user, project).filter(original__isnull=True),
            "versions": project.versions.select_related("file").order_by("-number"),
            "latest_version": project.versions.order_by("-number").first(),
            "revisions": project.revisions.select_related("version").order_by("-created_at"),
            "submission_files": project.files.filter(
                state="ready",
                uploader=request.user,
                category__in=["draft", "final"],
                projectversion__isnull=True,
            ),
            "review_enabled": project.order.terms_snapshot.get("review_rule") == "latest_request_v1",
            "revision_limit": project.order.terms_snapshot.get("revision_limit"),
            "upload_categories": allowed,
            "upload_policy": policy,
            "max_upload_mb": policy.max_bytes // 1048576 if policy else 0,
            "current_assignment": project.assignments.filter(ended_at__isnull=True)
            .select_related("editor__user")
            .first(),
        },
    )


@role_required("client")
def payment_history(request):
    return render(
        request,
        "client/payments.html",
        {
            "title": "Payment history",
            "payments": Payment.objects.filter(order__project__client__user=request.user).select_related(
                "order__project"
            ),
        },
    )


@require_GET
@role_required("client", "editor", "admin")
def project_api(request, project_id):
    project = project_for(request.user, project_id)
    return JsonResponse(
        {
            "id": str(project.id),
            "title": project.title,
            "status": project.status,
            "files": [
                {"id": str(f.id), "filename": f.filename, "size_bytes": f.size_bytes}
                for f in visible_files(request.user, project)
            ],
        }
    )


@require_GET
@role_required("client", "editor", "admin")
def area_api(request, area):
    if request.user.role != area:
        raise PermissionDenied
    return JsonResponse(
        {"role": area, "projects": list(visible_projects(request.user).values("id", "title", "status"))}
    )


@require_POST
@role_required("client", "editor")
def request_upload(request, project_id):
    project = project_for(request.user, project_id)
    policy = UploadPolicy.objects.filter(pk=1, enabled=True).first()
    if not policy:
        return JsonResponse({"error": "Uploads are not configured yet."}, status=503)
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict):
            raise ValueError
        filename = data["filename"]
        size = data["size_bytes"]
        digest = data["sha256"]
        content_type = data["content_type"]
        category = data["category"]
        if (
            not isinstance(filename, str)
            or not 1 <= len(filename) <= 240
            or any(c in filename for c in ["/", "\\", "\r", "\n", "\x00"])
        ):
            raise ValueError
        if type(size) is not int or not 0 < size <= policy.max_bytes:
            raise ValueError
        if not isinstance(digest, str) or not re.fullmatch("[0-9a-f]{64}", digest):
            raise ValueError
        suffix = PurePath(filename).suffix.lower()
        if not isinstance(content_type, str) or content_type not in policy.allowed_types.get(suffix, []):
            raise ValueError
    except (ValueError, KeyError, TypeError):
        return JsonResponse(
            {"error": "Invalid upload. Check file name, supported type, size and checksum."}, status=400
        )
    if not can_upload(request.user, project, category):
        raise PermissionDenied
    file_id = uuid.uuid4()
    file = File(
        id=file_id,
        project=project,
        uploader=request.user,
        filename=filename,
        size_bytes=size,
        sha256=digest,
        content_type=content_type,
        category=category,
        object_key=f"projects/{project.id}/{file_id}",
        expires_at=timezone.now() + timedelta(seconds=settings.UPLOAD_TTL_SECONDS),
    )
    try:
        permission = upload_permission(file)
        with transaction.atomic():
            file.save()
            audit(request.user, "file.upload_reserved", file.id)
    except (BotoCoreError, ClientError):
        return JsonResponse({"error": "Storage is unavailable. Please try again."}, status=503)
    return JsonResponse({"file_id": str(file.id), "upload": permission}, status=201)


@require_POST
@role_required("client", "editor")
def complete_upload(request, file_id):
    file = get_object_or_404(File, pk=file_id, uploader=request.user)
    project = project_for(request.user, file.project_id)
    if not can_upload(request.user, project, file.category):
        raise PermissionDenied
    if file.state == "ready":
        return JsonResponse({"file_id": str(file.id), "state": "ready"})
    if file.state != "pending" or file.expires_at < timezone.now():
        return JsonResponse({"error": "This upload permission expired. Start a new upload."}, status=409)
    try:
        metadata = inspect_object(file)
    except (ClientError, BotoCoreError):
        return JsonResponse(
            {"error": "Upload is not complete or storage is unavailable. Retry verification."}, status=409
        )
    expected = base64.b64encode(bytes.fromhex(file.sha256)).decode()
    if (
        metadata.get("ContentLength") != file.size_bytes
        or metadata.get("ContentType") != file.content_type
        or metadata.get("ChecksumSHA256") != expected
        or not metadata.get("VersionId")
        or metadata["VersionId"] == "null"
    ):
        File.objects.filter(pk=file.pk, state="pending").update(state="rejected")
        return JsonResponse(
            {"error": "Storage integrity verification failed. File was not accepted."}, status=409
        )
    with transaction.atomic():
        updated = File.objects.filter(pk=file.pk, state="pending").update(
            state="ready", storage_version=metadata["VersionId"], completed_at=timezone.now()
        )
        if updated:
            audit(
                request.user,
                "file.upload_completed",
                file.id,
                {"bytes": file.size_bytes, "sha256": file.sha256},
            )
    return JsonResponse({"file_id": str(file.id), "state": "ready"})


@require_POST
@role_required("client", "editor", "admin")
def request_download(request, file_id):
    file = get_object_or_404(File, pk=file_id, state="ready")
    project = project_for(request.user, file.project_id)
    get_object_or_404(visible_files(request.user, project), pk=file.pk)
    try:
        url = download_permission(file)
    except (ClientError, BotoCoreError):
        return JsonResponse({"error": "Download is temporarily unavailable."}, status=503)
    audit(request.user, "file.download_authorized", file.id)
    return JsonResponse({"url": url, "expires_in": settings.DOWNLOAD_TTL_SECONDS})


def forbidden(request, exception=None):
    if request.path.startswith("/api/"):
        return JsonResponse({"error": "Permission denied."}, status=403)
    return render(
        request,
        "error.html",
        {
            "title": "Permission denied",
            "error_code": 403,
            "message": "This page is not available for your account.",
            "detail": "Return to your workspace and choose a project or action available to your role.",
        },
        status=403,
    )


def not_found(request, exception=None):
    if request.path.startswith("/api/"):
        return JsonResponse({"error": "Not found."}, status=404)
    return render(
        request,
        "error.html",
        {
            "title": "Page not found",
            "error_code": 404,
            "message": "This page could not be found.",
            "detail": "The link may be outdated, or the project may no longer be available to your account.",
        },
        status=404,
    )


def server_error(request):
    if request.path.startswith("/api/"):
        return JsonResponse({"error": "Service temporarily unavailable."}, status=500)
    return render(
        request,
        "error.html",
        {
            "title": "Temporary service problem",
            "error_code": 500,
            "message": "We could not complete that request.",
            "detail": "Your saved work is unchanged. Try this page again, or return to your workspace.",
            "retry": True,
        },
        status=500,
    )
