"""Aggregate identity/profile/session consistency checks without personal data."""

import uuid

from django.contrib.auth import SESSION_KEY
from django.contrib.sessions.models import Session
from django.db.models import Q
from django.utils import timezone

from operations.models import Admin, Editor

from .models import Client, User


def _authenticated_session_users():
    user_ids = set()
    invalid_identifiers = 0
    for session in Session.objects.filter(expire_date__gt=timezone.now()).iterator(chunk_size=100):
        raw_user_id = session.get_decoded().get(SESSION_KEY)
        if raw_user_id is None:
            continue
        try:
            user_ids.add(uuid.UUID(str(raw_user_id)))
        except (TypeError, ValueError, AttributeError):
            invalid_identifiers += 1
    existing = User.objects.in_bulk(user_ids)
    missing_users = len(user_ids - set(existing))
    inactive_users = sum(not user.is_active for user in existing.values())
    return {
        "authenticated_sessions": len(user_ids) + invalid_identifiers,
        "invalid_session_user_identifiers": invalid_identifiers,
        "sessions_for_missing_users": missing_users,
        "sessions_for_inactive_users": inactive_users,
    }


def account_reconciliation_report():
    critical = {
        "client_role_missing_profile": User.objects.filter(
            role=User.Role.CLIENT, client_profile__isnull=True
        ).count(),
        "editor_role_missing_profile": User.objects.filter(
            role=User.Role.EDITOR, editor_profile__isnull=True
        ).count(),
        "admin_role_missing_profile": User.objects.filter(
            role=User.Role.ADMIN, admin_profile__isnull=True
        ).count(),
        "client_profile_role_mismatch": Client.objects.exclude(user__role=User.Role.CLIENT).count(),
        "editor_profile_role_mismatch": Editor.objects.exclude(user__role=User.Role.EDITOR).count(),
        "admin_profile_role_mismatch": Admin.objects.exclude(user__role=User.Role.ADMIN).count(),
        "users_with_multiple_profiles": User.objects.filter(
            Q(client_profile__isnull=False, editor_profile__isnull=False)
            | Q(client_profile__isnull=False, admin_profile__isnull=False)
            | Q(editor_profile__isnull=False, admin_profile__isnull=False)
        ).count(),
        "editors_missing_availability": Editor.objects.filter(availability__isnull=True).count(),
        "editors_missing_wallet": Editor.objects.filter(wallet__isnull=True).count(),
        "approved_editors_missing_review": Editor.objects.filter(approved=True).filter(
            Q(proficiency__isnull=True) | Q(approved_by__isnull=True)
        ).count(),
        "application_users_with_django_admin_flags": User.objects.filter(
            Q(is_staff=True) | Q(is_superuser=True)
        ).count(),
    }
    sessions = _authenticated_session_users()
    critical.update(
        {
            key: sessions[key]
            for key in (
                "invalid_session_user_identifiers",
                "sessions_for_missing_users",
                "sessions_for_inactive_users",
            )
        }
    )
    warnings = {
        "active_unverified_clients": User.objects.filter(
            role=User.Role.CLIENT,
            is_active=True,
            email_verified_at__isnull=True,
        ).count(),
        "inactive_approved_editors": Editor.objects.filter(
            approved=True, user__is_active=False
        ).count(),
    }
    critical_count = sum(critical.values())
    return {
        "status": "pass" if critical_count == 0 else "fail",
        "code": "accounts_consistent" if critical_count == 0 else "account_reconciliation_failed",
        "user_count": User.objects.count(),
        "client_count": Client.objects.count(),
        "editor_count": Editor.objects.count(),
        "admin_count": Admin.objects.count(),
        "authenticated_sessions": sessions["authenticated_sessions"],
        "critical": critical,
        "warnings": warnings,
        "critical_count": critical_count,
        "warning_count": sum(warnings.values()),
    }
