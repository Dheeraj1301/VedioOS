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
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .email_verification import (
    VerificationCooldown,
    VerificationServiceUnavailable,
    check_verification_code,
    send_verification_email,
)
from .forms import LoginForm, ProjectForm, RegistrationForm
from .models import (
    AuthAttempt,
    Client,
    File,
    InfluencerPackage,
    Order,
    Plan,
    Project,
    UploadPolicy,
    User,
)
from .payment_history import PAYMENT_STATUSES, payment_page
from .permissions import can_upload, project_for, role_required, visible_files, visible_projects
from .storage import download_permission, inspect_object, upload_permission

FONT_REFERENCE_MAX_BYTES = 1024 * 1024
FONT_IMAGE_EXTENSIONS = {".avif", ".bmp", ".gif", ".heic", ".heif", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}
INSPIRATION_UPLOAD_LIMIT = 3


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
                    user.is_active = False
                    user.save()
                    Client.objects.create(user=user)
                    audit(user, "client.registered", user.pk)
                request.session["verification_email"] = user.email
                try:
                    send_verification_email(user.email)
                except Exception:
                    messages.error(
                        request,
                        "Your account was saved, but the verification email could not be sent. Try resending it.",
                    )
                return redirect("verification_pending")
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


@require_GET
def verification_pending(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(
        request,
        "verification_pending.html",
        {
            "title": "Verify your email",
            "verification_email": request.session.get("verification_email", ""),
        },
    )


@require_POST
def resend_verification(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    if auth_rate_limited(request):
        return render(
            request,
            "error.html",
            {"message": "Too many attempts. Please try again in 15 minutes."},
            status=429,
        )
    email = request.POST.get("email", "").strip().lower()[:254]
    user = User.objects.filter(
        email__iexact=email,
        role="client",
        is_active=False,
        email_verified_at__isnull=True,
    ).first()
    if user:
        try:
            send_verification_email(user.email)
        except VerificationCooldown:
            pass
        except Exception:
            pass
    request.session["verification_email"] = email
    messages.success(
        request,
        "If an eligible unverified client account matches that email, a verification code has been sent.",
    )
    return redirect("verification_pending")


@require_POST
def verify_email_otp(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    if auth_rate_limited(request):
        return render(
            request,
            "error.html",
            {"message": "Too many attempts. Please try again in 15 minutes."},
            status=429,
        )
    email = request.POST.get("email", "").strip().lower()[:254]
    code = request.POST.get("code", "").strip()
    request.session["verification_email"] = email
    if not re.fullmatch(r"\d{6}", code):
        messages.error(request, "Enter the six digit code from your email.")
        return redirect("verification_pending")

    user = User.objects.filter(
        email__iexact=email,
        role="client",
        is_active=False,
        email_verified_at__isnull=True,
    ).first()
    try:
        result = check_verification_code(email, code) if user else "invalid"
    except VerificationServiceUnavailable:
        messages.error(request, "Email verification is temporarily unavailable. Try again shortly.")
        return redirect("verification_pending")

    with transaction.atomic():
        user = (
            User.objects.select_for_update()
            .filter(pk=user.pk, is_active=False, email_verified_at__isnull=True)
            .first()
            if user
            else None
        )
        if result == "verified":
            if user is None:
                result = "invalid"
            else:
                user.email_verified_at = timezone.now()
                user.is_active = True
                user.save(update_fields=["email_verified_at", "is_active"])
                audit(user, "client.email_verified", user.pk, {"method": "supabase_email_otp"})

    if result != "verified":
        detail = {
            "expired": "That code has expired. Request a new code.",
            "locked": "Too many incorrect attempts. Request a new code.",
        }.get(result, "That code is invalid. Check the email and try again.")
        messages.error(request, detail)
        return redirect("verification_pending")

    login(request, user)
    request.session.pop("verification_email", None)
    messages.success(request, "Email verified. Your client workspace is ready.")
    return redirect("client_dashboard")


def _login_view(request, *, editor_only=False):
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
        user = form.get_user()
        if editor_only and user.role != "editor":
            form.add_error(
                None,
                "This sign-in is for editor accounts. Use the regular sign-in page for this account.",
            )
        else:
            login(request, user)
            return redirect("editor_dashboard" if editor_only else "dashboard")
    return render(
        request,
        "auth.html",
        {
            "form": form,
            "title": "Editor sign in." if editor_only else "Back to your next great edit.",
            "subtitle": (
                "Use your administrator-issued editor ID or editor email."
                if editor_only
                else "Sign in to your VedioOS workspace."
            ),
            "button": "Editor Sign In" if editor_only else "Log in",
            "mode": "editor_login" if editor_only else "login",
        },
    )


def login_view(request):
    return _login_view(request)


def editor_login_view(request):
    return _login_view(request, editor_only=True)


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
    # The overview is a persistent status screen, not a flash-message inbox.
    # Consume queued notices so redirects and repeated form submissions cannot
    # stack stale banners above the dashboard content.
    list(messages.get_messages(request))
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
    create_new = request.GET.get("new") == "1"
    project = None
    if not create_new:
        active_project_id = request.session.get("active_project_draft_id")
        if active_project_id:
            project = request.user.client_profile.projects.filter(
                pk=active_project_id,
                status="payment_pending",
                order__payment_status="pending",
                order__terms_snapshot={},
            ).select_related("order").first()
    return _project_form(request, project, create_new=create_new)


@role_required("client")
def edit_project(request, project_id):
    project = get_object_or_404(
        request.user.client_profile.projects.select_related("order"), pk=project_id
    )
    if (
        project.status != "payment_pending"
        or project.order.payment_status != "pending"
        or project.order.terms_snapshot
    ):
        raise PermissionDenied
    return _project_form(request, project)


def _project_form(request, project=None, *, create_new=False):
    is_new = project is None
    form = ProjectForm(request.POST or None, instance=project)
    if request.method == "POST" and form.is_valid():
        quote = None
        quote_error = ""
        with transaction.atomic():
            saved_project = form.save(commit=False)
            selected_plan = form.cleaned_data.get("selected_plan")
            if selected_plan:
                saved_project.quotation_snapshot = {}
            else:
                try:
                    from .commerce import saved_custom_estimate_snapshot

                    saved_project.quotation_snapshot = saved_custom_estimate_snapshot(
                        form.cleaned_data, lock=True
                    )
                except ValidationError:
                    # Draft creation remains available while commercial configuration is incomplete.
                    saved_project.quotation_snapshot = {}
            existing_order = None
            if not is_new:
                locked_project = Project.objects.select_for_update().get(
                    pk=saved_project.pk, client=request.user.client_profile
                )
                existing_order = Order.objects.select_for_update().get(project=locked_project)
                if (
                    locked_project.status != "payment_pending"
                    or existing_order.payment_status != "pending"
                    or existing_order.terms_snapshot
                ):
                    raise PermissionDenied
            if is_new:
                saved_project.client = request.user.client_profile
            saved_project.save()
            pricing_period = (
                form.cleaned_data["pricing_period"]
                if selected_plan
                else Plan.PricingPeriod.PER_REEL
            )
            if is_new:
                Order.objects.create(
                    project=saved_project,
                    kind="plan" if selected_plan else "custom",
                    plan=selected_plan,
                    pricing_period=pricing_period,
                )
                action = "project.draft_created"
            else:
                existing_order.kind = "plan" if selected_plan else "custom"
                existing_order.plan = selected_plan
                existing_order.pricing_period = pricing_period
                existing_order.save(
                    update_fields=["kind", "plan", "pricing_period", "updated_at"]
                )
                action = "project.brief_updated"
            if not selected_plan and saved_project.quotation_snapshot:
                try:
                    from .commerce import create_quote

                    quote = create_quote(request.user, saved_project.pk, "custom")
                except ValidationError as exc:
                    quote_error = " ".join(exc.messages)
            audit(request.user, action, saved_project.pk)
        request.session["active_project_draft_id"] = str(saved_project.pk)
        if not selected_plan:
            if quote:
                messages.success(request, "Creative brief and quotation saved.")
            else:
                messages.error(
                    request,
                    quote_error
                    or "A valid quotation could not be generated. Review the pricing configuration and try again.",
                )
            return redirect("custom_checkout", project_id=saved_project.pk)
        messages.success(request, "Creative brief saved. Add or review your private files below.")
        return redirect("client_project", project_id=saved_project.pk)
    slots = {plan.slot: plan for plan in Plan.objects.order_by("slot")}
    plan_slots = [
        (slot, slots.get(slot), f"plan:{slots[slot].pk}" if slots.get(slot) else "")
        for slot in range(1, 4)
    ]
    active_inspiration_count = 0
    existing_brief_files = File.objects.none()
    if project:
        active_inspiration_count = project.files.filter(category="reference").filter(
            Q(state="ready") | Q(state="pending", expires_at__gt=timezone.now())
        ).count()
        existing_brief_files = visible_files(request.user, project).filter(
            original__isnull=True,
            category__in=["source", "image", "audio", "reference", "font_reference", "asset"],
        )
    upload_policy = UploadPolicy.objects.filter(pk=1, enabled=True).first()
    return render(
        request,
        "client/new_order.html",
        {
            "form": form,
            "title": "Plan a new edit",
            "project": project,
            "create_new": create_new,
            "selected_choice": form["order_choice"].value() or "",
            "selected_pricing_period": (
                form["pricing_period"].value() or Plan.PricingPeriod.PER_REEL
            ),
            "plan_slots": plan_slots,
            "active_inspiration_count": active_inspiration_count,
            "existing_brief_files": existing_brief_files,
            "upload_policy": upload_policy,
            "monthly_packages": InfluencerPackage.objects.filter(active=True).order_by("name"),
        },
    )


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
            ("font_reference", "Font inspiration"),
            ("asset", "Other asset"),
        ]
        if area == "client"
        else [("draft", "Edited draft"), ("final", "Final video")]
    )
    allowed = [(key, label) for key, label in categories if can_upload(request.user, project, key)]
    from operations.messages import message_page

    project_messages, older_cursor = message_page(request.user, project, request.GET.get("messages_before"))
    active_inspiration_count = project.files.filter(category="reference").filter(
        Q(state="ready") | Q(state="pending", expires_at__gt=timezone.now())
    ).count()

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
            "source_upload_categories": [
                item for item in allowed if item[0] not in ["reference", "font_reference"]
            ],
            "can_upload_inspiration": any(item[0] == "reference" for item in allowed),
            "can_upload_font_inspiration": any(
                item[0] == "font_reference" for item in allowed
            ) and project.wants_wording and project.wording_direction == "font_inspiration",
            "upload_policy": policy,
            "max_upload_mb": policy.max_bytes // 1048576 if policy else 0,
            "active_inspiration_count": active_inspiration_count,
            "inspiration_upload_limit": INSPIRATION_UPLOAD_LIMIT,
            "current_assignment": project.assignments.filter(ended_at__isnull=True)
            .select_related("editor__user")
            .first(),
            "ready_file_count": project.files.filter(state="ready").count(),
            "open_revision_count": project.revisions.filter(
                status__in=["requested", "in_progress"]
            ).count(),
        },
    )


@role_required("client")
def payment_history(request):
    payments, older_cursor, payment_filter = payment_page(
        request.user, request.GET.get("before"), request.GET.get("status", "all")
    )
    return render(
        request,
        "client/payments.html",
        {
            "title": "Payment history",
            "payments": payments,
            "older_payment_cursor": older_cursor,
            "payment_filter": payment_filter,
            "payment_statuses": PAYMENT_STATUSES,
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
                {
                    "id": str(f.id),
                    "filename": f.filename,
                    "size_bytes": f.size_bytes,
                    "category": f.category,
                    "category_label": f.get_category_display(),
                }
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
        if not can_upload(request.user, project, category):
            raise PermissionDenied
        suffix = PurePath(filename).suffix.lower()
        if not isinstance(content_type, str) or not 1 <= len(content_type) <= 100:
            raise ValueError
        if category == "font_reference":
            if (
                size >= FONT_REFERENCE_MAX_BYTES
                or suffix not in FONT_IMAGE_EXTENSIONS
                or not content_type.startswith("image/")
            ):
                raise ValueError
        elif category not in ["reference", "source"] and content_type not in policy.allowed_types.get(suffix, []):
            raise ValueError
    except (ValueError, KeyError, TypeError):
        return JsonResponse(
            {"error": "Invalid upload. Check file name, supported type, size and checksum."}, status=400
        )
    try:
        with transaction.atomic():
            if category == "reference":
                locked_project = Project.objects.select_for_update().get(pk=project.pk)
                active_count = File.objects.filter(
                    project=locked_project, category="reference"
                ).filter(
                    Q(state="ready") | Q(state="pending", expires_at__gt=timezone.now())
                ).count()
                if active_count >= INSPIRATION_UPLOAD_LIMIT:
                    return JsonResponse(
                        {"error": "Max uploads: 3"}, status=409
                    )
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
            permission = upload_permission(file)
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
    try:
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
            version = None
            if request.user.role == "editor" and file.category in ["draft", "final"]:
                from .delivery import transition

                if project.status in ["editor_assigned", "revision_requested"]:
                    transition(request.user, project.pk, "start")
                transition(
                    request.user,
                    project.pk,
                    "submit",
                    file_id=file.pk,
                    final=file.category == "final",
                    use_latest=True,
                )
                version = file.projectversion
    except ValidationError as exc:
        return JsonResponse({"error": exc.messages[0]}, status=409)
    response = {"file_id": str(file.id), "state": "ready"}
    if version:
        response["version"] = version.number
        response["available_to_client"] = True
    return JsonResponse(response)


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
