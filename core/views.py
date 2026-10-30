import base64
import hashlib
import json
import re
import uuid
from datetime import datetime, timedelta
from pathlib import PurePath

from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.sessions.models import Session
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
    check_password_reset_code,
    check_verification_code,
    send_password_reset_email,
    send_verification_email,
)
from .forms import LoginForm, PasswordResetSetForm, ProjectForm, RegistrationForm
from .landing_content import landing_content, landing_faqs
from .models import (
    AuthAttempt,
    Client,
    CommercePolicy,
    File,
    LandingPageSettings,
    Order,
    Plan,
    Project,
    UploadPolicy,
    User,
)
from .payment_history import PAYMENT_DATE_RANGES, payment_page
from .permissions import can_upload, project_for, role_required, visible_files, visible_projects
from .policies import policy_snapshot, record_registration_acceptance, validate_policy_version
from .sessions import (
    active_session_exists,
    clear_pending_login,
    establish_session,
    pending_login,
    remember_pending_login,
)
from .storage import delete_private_object_versions, download_permission, inspect_object, upload_permission
from .v1 import v1_status

FONT_REFERENCE_MAX_BYTES = 1024 * 1024
FONT_IMAGE_EXTENSIONS = {".avif", ".bmp", ".gif", ".heic", ".heif", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}
INSPIRATION_UPLOAD_LIMIT = 3
PASSWORD_RESET_GRANT_MINUTES = 10


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
    config = LandingPageSettings.objects.filter(pk=1).first()
    saved_content = config.content if config else None
    return render(
        request,
        "landing.html",
        {
            "plans": Plan.objects.filter(active=True),
            "landing_content": landing_content(saved_content),
            "landing_faqs": [faq for faq in landing_faqs(saved_content) if faq.get("published")],
            "landing_has_video": bool(config and config.hero_video_object_key),
        },
    )


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
    policy = CommercePolicy.objects.filter(pk=1).first()
    current_policy = policy_snapshot(policy or CommercePolicy())
    if not policy:
        current_policy["version"] = 0
    policy_acknowledged = request.POST.get("accept_terms") == "yes"
    if request.method == "POST":
        if any(
            key in request.POST for key in ["role", "is_staff", "is_superuser", "approved", "proficiency"]
        ):
            raise PermissionDenied("Account permissions cannot be set during registration.")
        if not policy_acknowledged:
            form.add_error(None, "Review and accept the Terms and Conditions to create an account.")
        else:
            try:
                validate_policy_version(current_policy, request.POST.get("policy_version"))
            except ValidationError as exc:
                form.add_error(None, exc.messages[0])
        if form.is_valid() and not form.non_field_errors():
            try:
                with transaction.atomic():
                    user = form.save(commit=False)
                    user.role = "client"
                    user.is_active = False
                    user.save()
                    Client.objects.create(user=user)
                    record_registration_acceptance(user, request.POST.get("policy_version"))
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
            "policy": current_policy,
            "policy_acknowledged": policy_acknowledged and not form.non_field_errors(),
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
    known_email = request.session.get("verification_email", "").lower() == email
    resend_state = "sent"
    if user:
        try:
            send_verification_email(user.email)
        except VerificationCooldown:
            resend_state = "cooldown"
        except Exception:
            resend_state = "unavailable"
    request.session["verification_email"] = email
    if known_email and resend_state == "cooldown":
        messages.info(
            request,
            "A code was requested recently. Wait a moment, then check your inbox again.",
        )
    elif known_email and resend_state == "unavailable":
        messages.error(request, "We could not send a new code right now. Please try again shortly.")
    else:
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

    establish_session(request, user)
    request.session.pop("verification_email", None)
    return redirect("verification_success")


@require_GET
def verification_success(request):
    if not request.user.is_authenticated:
        return redirect("login")
    return render(request, "verification_success.html", {"title": "Email verified"})


def _password_reset_user(request):
    user_id = request.session.get("password_reset_user_id")
    verified_at = request.session.get("password_reset_verified_at")
    try:
        verified = datetime.fromisoformat(verified_at)
        if timezone.is_naive(verified):
            verified = timezone.make_aware(verified)
    except (TypeError, ValueError):
        return None
    if verified < timezone.now() - timedelta(minutes=PASSWORD_RESET_GRANT_MINUTES):
        return None
    return User.objects.filter(
        pk=user_id,
        role__in=[User.Role.CLIENT, User.Role.EDITOR],
        is_active=True,
    ).first()


def _clear_password_reset(request):
    for key in [
        "password_reset_email",
        "password_reset_user_id",
        "password_reset_verified_at",
        "password_reset_role",
        "password_reset_origin",
    ]:
        request.session.pop(key, None)


def password_reset_request(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    if request.method == "POST" and auth_rate_limited(request):
        return render(
            request,
            "error.html",
            {"message": "Too many attempts. Please try again in 15 minutes."},
            status=429,
        )
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()[:254]
        origin = "editor" if request.POST.get("origin") == "editor" else "client"
        user = User.objects.filter(
            email__iexact=email,
            role__in=[User.Role.CLIENT, User.Role.EDITOR],
            is_active=True,
        ).first()
        _clear_password_reset(request)
        request.session["password_reset_email"] = email
        request.session["password_reset_origin"] = origin
        if user:
            try:
                if user.role == User.Role.EDITOR:
                    send_verification_email(user.email)
                else:
                    send_password_reset_email(user.email)
            except (VerificationCooldown, VerificationServiceUnavailable):
                # Keep the response identical so provider state cannot reveal account existence.
                pass
        messages.success(
            request,
            "If an eligible account matches that email, a six-digit reset code has been sent.",
        )
        return redirect("password_reset_verify")
    origin = (
        "editor"
        if request.GET.get("from") == "editor"
        or request.session.get("password_reset_origin") == "editor"
        else "client"
    )
    request.session["password_reset_origin"] = origin
    return render(
        request,
        "password_reset_request.html",
        {"title": "Reset your password", "password_reset_origin": origin},
    )


def password_reset_verify(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    email = request.session.get("password_reset_email", "")
    if not email:
        return redirect("password_reset_request")
    if request.method == "POST" and auth_rate_limited(request):
        return render(
            request,
            "error.html",
            {"message": "Too many attempts. Please try again in 15 minutes."},
            status=429,
        )
    if request.method == "POST":
        code = request.POST.get("code", "").strip()
        if not re.fullmatch(r"\d{6}", code):
            messages.error(request, "Enter the six digit code from your email.")
            return redirect("password_reset_verify")
        user = User.objects.filter(
            email__iexact=email,
            role__in=[User.Role.CLIENT, User.Role.EDITOR],
            is_active=True,
        ).first()
        try:
            result = (
                check_password_reset_code(
                    email,
                    code,
                    code_type="email" if user.role == User.Role.EDITOR else "recovery",
                )
                if user
                else "invalid"
            )
        except VerificationServiceUnavailable:
            messages.error(request, "Password recovery is temporarily unavailable. Try again shortly.")
            return redirect("password_reset_verify")
        if result == "verified" and user:
            request.session["password_reset_user_id"] = str(user.pk)
            request.session["password_reset_verified_at"] = timezone.now().isoformat()
            request.session["password_reset_role"] = user.role
            return redirect("password_reset_new")
        detail = {
            "expired": "That code has expired. Request a new code.",
            "locked": "Too many incorrect attempts. Request a new code.",
        }.get(result, "That code is invalid. Check the email and try again.")
        messages.error(request, detail)
        return redirect("password_reset_verify")
    return render(
        request,
        "password_reset_verify.html",
        {
            "title": "Enter your reset code",
            "password_reset_email": email,
            "password_reset_origin": request.session.get(
                "password_reset_origin", "client"
            ),
        },
    )


def password_reset_new(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    user = _password_reset_user(request)
    if not user:
        _clear_password_reset(request)
        messages.error(request, "Your verified reset session expired. Request a new code.")
        return redirect("password_reset_request")
    if request.method == "POST" and auth_rate_limited(request):
        return render(
            request,
            "error.html",
            {"message": "Too many attempts. Please try again in 15 minutes."},
            status=429,
        )
    form = PasswordResetSetForm(user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            locked_user = User.objects.select_for_update().get(
                pk=user.pk,
                role__in=[User.Role.CLIENT, User.Role.EDITOR],
                is_active=True,
            )
            previous_session_key = locked_user.active_session_key
            locked_user.set_password(form.cleaned_data["new_password1"])
            locked_user.active_session_key = ""
            locked_user.save(update_fields=["password", "active_session_key"])
            if previous_session_key:
                Session.objects.filter(session_key=previous_session_key).delete()
            audit(
                locked_user,
                f"{locked_user.role}.password_reset",
                locked_user.pk,
                {"method": "supabase_email_otp"},
            )
        destination = "editor_login" if locked_user.role == User.Role.EDITOR else "login"
        _clear_password_reset(request)
        messages.success(request, "Your password has been reset. Log in with your new password.")
        return redirect(destination)
    return render(
        request,
        "password_reset_new.html",
        {"title": "Choose a new password", "form": form},
    )


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
            if active_session_exists(user) and user.active_session_key != request.session.session_key:
                destination = "editor_dashboard" if editor_only else "dashboard"
                remember_pending_login(request, user, destination)
                return render(
                    request,
                    "session_conflict.html",
                    {"title": "Account already in use", "editor_only": editor_only},
                    status=409,
                )
            establish_session(request, user)
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
                else "Sign in to your BRIO workspace."
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
def session_decision(request):
    user, destination = pending_login(request)
    action = request.POST.get("action")
    if action == "keep" or user is None:
        clear_pending_login(request)
        messages.info(request, "The other device remains signed in. No changes were made.")
        return redirect("login")
    if action != "replace":
        raise PermissionDenied("Choose a valid session option.")
    establish_session(request, user)
    audit(user, "account.session_replaced", user.pk)
    messages.success(request, "This device is now signed in. The previous session has ended.")
    return redirect(destination)


@require_POST
def logout_view(request):
    if request.user.is_authenticated:
        User.objects.filter(
            pk=request.user.pk,
            active_session_key=request.session.session_key,
        ).update(active_session_key="")
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
        or project.order.payments.filter(status="confirmed").exists()
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
                saved_project.song_information = form.cleaned_data[
                    "standard_song_preference"
                ].strip()
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
                    or existing_order.payments.filter(status="confirmed").exists()
                ):
                    raise PermissionDenied
                if existing_order.terms_snapshot:
                    for payment in existing_order.payments.select_for_update().filter(
                        status="pending"
                    ):
                        payment.status = "cancelled"
                        payment.save(update_fields=["status", "updated_at"])
                        audit(
                            request.user,
                            "payment.cancelled_for_brief_edit",
                            payment.id,
                            {"order": str(existing_order.id)},
                        )
                    existing_order.terms_snapshot = {}
                    existing_order.total_minor = None
                    existing_order.currency = ""
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
                    update_fields=[
                        "kind",
                        "plan",
                        "pricing_period",
                        "terms_snapshot",
                        "total_minor",
                        "currency",
                        "updated_at",
                    ]
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
            if not quote:
                messages.error(
                    request,
                    quote_error
                    or "A valid quotation could not be generated. Review the pricing configuration and try again.",
                )
            return redirect("order_summary", project_id=saved_project.pk)
        try:
            from .commerce import accept_quote, create_quote

            quote = create_quote(
                request.user,
                saved_project.pk,
                "plan",
                plan_id=selected_plan.pk,
                pricing_period=pricing_period,
            )
            accept_quote(request.user, saved_project.pk, quote.id)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
            return redirect("client_project", project_id=saved_project.pk)
        messages.success(request, "Creative brief and fixed plan price saved. Continue to payment.")
        return redirect("order_summary", project_id=saved_project.pk)
    if request.method == "POST" and request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse(
            {
                "errors": {
                    field: [error["message"] for error in errors]
                    for field, errors in form.errors.get_json_data().items()
                }
            },
            status=422,
        )
    slots = {plan.slot: plan for plan in Plan.objects.order_by("slot")}
    plan_slots = [
        (slot, slots.get(slot), f"plan:{slots[slot].pk}" if slots.get(slot) else "")
        for slot in range(1, 4)
    ]
    active_inspiration_count = 0
    existing_brief_files = File.objects.none()
    standard_existing_brief_files = File.objects.none()
    if project:
        active_inspiration_count = project.files.filter(category="reference").filter(
            Q(state="ready") | Q(state="pending", expires_at__gt=timezone.now())
        ).count()
        existing_brief_files = project.files.filter(
            uploader=request.user,
            original__isnull=True,
            category__in=["source", "image", "audio", "reference", "font_reference", "asset"],
        ).filter(Q(state="ready") | Q(state="pending", expires_at__gt=timezone.now()))
        if project.order.kind == "plan":
            standard_existing_brief_files = existing_brief_files
            existing_brief_files = File.objects.none()
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
            "plan_slots": plan_slots,
            "active_inspiration_count": active_inspiration_count,
            "existing_brief_files": existing_brief_files,
            "standard_existing_brief_files": standard_existing_brief_files,
            "upload_policy": upload_policy,
        },
    )


@role_required("client")
def my_projects(request):
    status_groups = {
        "pending": {
            Project.Status.PENDING,
            Project.Status.PAID,
            Project.Status.WAITING,
        },
        "ongoing": {
            Project.Status.ASSIGNED,
            Project.Status.EDITING,
            Project.Status.DRAFT,
            Project.Status.REVIEW,
            Project.Status.REVISION_REQUESTED,
            Project.Status.REVISING,
            Project.Status.FINAL,
        },
        "completed": {Project.Status.COMPLETED},
        "cancelled": {Project.Status.CANCELLED},
    }
    projects = list(visible_projects(request.user))
    for project in projects:
        project.client_status_group = next(
            (group for group, statuses in status_groups.items() if project.status in statuses),
            "ongoing",
        )
    return render(
        request,
        "projects.html",
        {
            "projects": projects,
            "title": "My projects",
            "project_status_filters": (
                ("all", "All"),
                ("pending", "Pending"),
                ("ongoing", "Ongoing"),
                ("completed", "Completed"),
                ("cancelled", "Cancelled"),
            ),
        },
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
    from operations.messages import message_page, messaging_enabled

    project_messages, older_cursor = message_page(request.user, project, request.GET.get("messages_before"))
    active_inspiration_count = project.files.filter(category="reference").filter(
        Q(state="ready") | Q(state="pending", expires_at__gt=timezone.now())
    ).count()

    version_status = v1_status(project)
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
            "messaging_enabled": messaging_enabled(project),
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
            **version_status,
        },
    )


@role_required("client")
def payment_history(request):
    payment_search = request.GET.get("q", "").strip()
    payment_date_range = request.GET.get("range", "all")
    payments, older_cursor, payment_filter = payment_page(
        request.user,
        request.GET.get("before"),
        request.GET.get("status", "all"),
        query=payment_search,
        date_range=payment_date_range,
    )
    if payment_date_range not in PAYMENT_DATE_RANGES:
        payment_date_range = "all"
    return render(
        request,
        "client/payments.html",
        {
            "title": "Payment history",
            "payments": payments,
            "older_payment_cursor": older_cursor,
            "payment_filter": payment_filter,
            "payment_search": payment_search,
            "payment_date_range": payment_date_range,
            "payment_date_label": PAYMENT_DATE_RANGES[payment_date_range][0],
            "payment_date_ranges": PAYMENT_DATE_RANGES,
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
@role_required("client")
@transaction.atomic
def remove_brief_file(request, file_id):
    file = get_object_or_404(
        File.objects.select_for_update().select_related("project__order"),
        pk=file_id,
        uploader=request.user,
        project__client__user=request.user,
        original__isnull=True,
        category__in=["source", "image", "audio", "reference", "font_reference", "asset"],
        state__in=["pending", "ready"],
    )
    project = file.project
    if (
        project.status != Project.Status.PENDING
        or project.order.payment_status != "pending"
        or hasattr(file, "projectversion")
    ):
        raise PermissionDenied
    try:
        delete_private_object_versions(file.object_key)
    except (ClientError, BotoCoreError):
        return JsonResponse(
            {
                "error": (
                    "The private file could not be removed from storage. "
                    "Please try again; its project record is unchanged."
                )
            },
            status=503,
        )
    updated = File.objects.filter(pk=file.pk, state__in=["pending", "ready"]).update(
        state="removed", updated_at=timezone.now()
    )
    if updated:
        audit(
            request.user,
            "file.removed_from_checkout" if project.order.terms_snapshot else "file.removed_from_brief",
            file.id,
            {"project": str(project.id), "category": file.category},
        )
    return JsonResponse({"file_id": str(file.id), "state": "removed"})


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
