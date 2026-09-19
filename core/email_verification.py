from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.urls import reverse

SALT = "vedioos.client-email-verification.v1"


def verification_token(user):
    return signing.dumps({"user_id": str(user.pk), "email": user.email}, salt=SALT, compress=True)


def verification_payload(token):
    return signing.loads(token, salt=SALT, max_age=settings.EMAIL_VERIFICATION_MAX_AGE)


def send_verification_email(request, user):
    url = request.build_absolute_uri(reverse("verify_email", args=[verification_token(user)]))
    send_mail(
        "Verify your VedioOS email",
        (
            f"Hello {user.name},\n\n"
            "Verify your email to activate your VedioOS client workspace:\n"
            f"{url}\n\n"
            f"This link expires in {settings.EMAIL_VERIFICATION_MAX_AGE // 3600} hours. "
            "If you did not create this account, you can ignore this message."
        ),
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
    )
