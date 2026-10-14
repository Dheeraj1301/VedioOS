"""Single-active-session coordination using Django's server-side session IDs."""

from datetime import datetime, timedelta

from django.contrib.auth import login
from django.contrib.sessions.models import Session
from django.db import transaction
from django.utils import timezone

from .models import User

PENDING_LOGIN_USER = "pending_login_user_id"
PENDING_LOGIN_DESTINATION = "pending_login_destination"
PENDING_LOGIN_AT = "pending_login_at"
PENDING_LOGIN_TTL = timedelta(minutes=5)


def active_session_exists(user):
    return (
        bool(user.active_session_key)
        and Session.objects.filter(
            session_key=user.active_session_key,
            expire_date__gt=timezone.now(),
        ).exists()
    )


def remember_pending_login(request, user, destination):
    request.session[PENDING_LOGIN_USER] = str(user.pk)
    request.session[PENDING_LOGIN_DESTINATION] = destination
    request.session[PENDING_LOGIN_AT] = timezone.now().isoformat()


def pending_login(request):
    user_id = request.session.get(PENDING_LOGIN_USER)
    issued_at = request.session.get(PENDING_LOGIN_AT)
    if not user_id or not issued_at:
        return None, "dashboard"
    try:
        issued = datetime.fromisoformat(issued_at)
    except (TypeError, ValueError):
        return None, "dashboard"
    if timezone.now() - issued > PENDING_LOGIN_TTL:
        clear_pending_login(request)
        return None, "dashboard"
    return User.objects.filter(pk=user_id, is_active=True).first(), request.session.get(
        PENDING_LOGIN_DESTINATION, "dashboard"
    )


def clear_pending_login(request):
    for key in [PENDING_LOGIN_USER, PENDING_LOGIN_DESTINATION, PENDING_LOGIN_AT]:
        request.session.pop(key, None)


def establish_session(request, user):
    """Log in and atomically designate this browser as the user's active session."""
    with transaction.atomic():
        locked_user = User.objects.select_for_update().get(pk=user.pk)
        login(request, locked_user)
        locked_user.active_session_key = request.session.session_key
        locked_user.save(update_fields=["active_session_key"])
    clear_pending_login(request)
    return locked_user
