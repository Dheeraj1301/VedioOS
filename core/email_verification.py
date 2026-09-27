import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core import signing
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import EmailVerificationChallenge, User

SALT = "vedioos.client-email-verification.v1"


def verification_token(user):
    return signing.dumps({"user_id": str(user.pk), "email": user.email}, salt=SALT, compress=True)


def verification_payload(token):
    return signing.loads(token, salt=SALT, max_age=settings.EMAIL_VERIFICATION_MAX_AGE)


class VerificationCooldown(Exception):
    pass


def _new_code():
    return f"{secrets.randbelow(1_000_000):06d}"


def issue_verification_code(user, *, enforce_cooldown=True):
    now = timezone.now()
    with transaction.atomic():
        locked_user = User.objects.select_for_update().get(pk=user.pk)
        challenge = EmailVerificationChallenge.objects.filter(user=locked_user).first()
        if (
            enforce_cooldown
            and challenge
            and challenge.sent_at
            > now - timedelta(seconds=settings.EMAIL_OTP_RESEND_SECONDS)
        ):
            raise VerificationCooldown
        code = _new_code()
        EmailVerificationChallenge.objects.update_or_create(
            user=locked_user,
            defaults={
                "code_hash": make_password(code),
                "expires_at": now + timedelta(seconds=settings.EMAIL_OTP_MAX_AGE_SECONDS),
                "sent_at": now,
                "attempts": 0,
            },
        )
    return code


def check_verification_code(user, code):
    """Return a stable result without storing or logging the plaintext code."""
    now = timezone.now()
    with transaction.atomic():
        challenge = (
            EmailVerificationChallenge.objects.select_for_update().filter(user=user).first()
        )
        if challenge is None:
            return "invalid"
        if challenge.expires_at <= now:
            return "expired"
        if challenge.attempts >= settings.EMAIL_OTP_MAX_ATTEMPTS:
            return "locked"
        if not check_password(code, challenge.code_hash):
            challenge.attempts += 1
            challenge.save(update_fields=["attempts", "updated_at"])
            return "locked" if challenge.attempts >= settings.EMAIL_OTP_MAX_ATTEMPTS else "invalid"
        challenge.delete()
        return "verified"


def send_verification_email(user, *, enforce_cooldown=True):
    code = issue_verification_code(user, enforce_cooldown=enforce_cooldown)
    send_mail(
        "Your VedioOS verification code",
        (
            f"Hello {user.name},\n\n"
            "Enter this code to activate your VedioOS client workspace:\n\n"
            f"{code}\n\n"
            f"This code expires in {settings.EMAIL_OTP_MAX_AGE_SECONDS // 60} minutes. "
            "If you did not create this account, you can ignore this message."
        ),
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )
