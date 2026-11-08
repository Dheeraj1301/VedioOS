"""Send Django email through the Gmail API with an OAuth refresh token (scope gmail.send)."""

import base64

import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

TOKEN_URL = "https://oauth2.googleapis.com/token"
SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


class GmailAPIBackend(BaseEmailBackend):
    def _access_token(self):
        response = requests.post(
            TOKEN_URL,
            data={
                "client_id": settings.GMAIL_CLIENT_ID,
                "client_secret": settings.GMAIL_CLIENT_SECRET,
                "refresh_token": settings.GMAIL_REFRESH_TOKEN,
                "grant_type": "refresh_token",
            },
            timeout=settings.EMAIL_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()["access_token"]

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        try:
            token = self._access_token()
        except Exception:
            if not self.fail_silently:
                raise
            return 0
        sent = 0
        for message in email_messages:
            raw = base64.urlsafe_b64encode(message.message().as_bytes()).decode("ascii")
            try:
                response = requests.post(
                    SEND_URL,
                    headers={"Authorization": f"Bearer {token}"},
                    json={"raw": raw},
                    timeout=settings.EMAIL_TIMEOUT,
                )
                response.raise_for_status()
                sent += 1
            except Exception:
                if not self.fail_silently:
                    raise
        return sent
