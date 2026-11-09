"""Timed alarms through Upstash QStash: wake the site at an exact moment to send reminders or expire projects.

An alarm only triggers the existing idempotent sweep, so a late, early or repeated alarm never double-sends.
Without QSTASH_TOKEN, scheduling is skipped and the daily cron and dashboard loads still run the sweep.
"""

import base64
import hashlib
import hmac
import json
import logging
import time

import requests
from django.conf import settings

logger = logging.getLogger(__name__)
TIMER_PATH = "/internal/timer/"


def timer_url():
    return settings.PUBLIC_SITE_URL + TIMER_PATH


def schedule_sweep(run_at, dedup_id):
    """Ask QStash to call the timer endpoint at run_at (an aware datetime). Returns True when accepted."""
    if not settings.QSTASH_TOKEN:
        return False
    try:
        response = requests.post(
            f"{settings.QSTASH_URL}/v2/publish/{timer_url()}",
            headers={
                "Authorization": f"Bearer {settings.QSTASH_TOKEN}",
                "Content-Type": "application/json",
                "Upstash-Not-Before": str(int(run_at.timestamp())),
                "Upstash-Deduplication-Id": dedup_id,
            },
            data="{}",
            timeout=10,
        )
        response.raise_for_status()
        return True
    except Exception:
        logger.exception("QStash alarm could not be scheduled")
        return False


def _b64decode(part):
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def _valid_with_key(token, key, body):
    try:
        header, payload, signature = token.split(".")
        if json.loads(_b64decode(header)).get("alg") != "HS256":
            return False
        expected = hmac.new(key.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64decode(signature)):
            return False
        claims = json.loads(_b64decode(payload))
    except Exception:
        return False
    now = time.time()
    body_hash = base64.urlsafe_b64encode(hashlib.sha256(body).digest()).decode().rstrip("=")
    return (
        claims.get("iss") == "Upstash"
        and claims.get("sub") == timer_url()
        and claims.get("nbf", 0) <= now + 60
        and claims.get("exp", 0) >= now - 60
        and str(claims.get("body", "")).rstrip("=") == body_hash
    )


def verify_request(request):
    token = request.headers.get("Upstash-Signature", "")
    keys = [k for k in (settings.QSTASH_CURRENT_SIGNING_KEY, settings.QSTASH_NEXT_SIGNING_KEY) if k]
    return bool(token) and any(_valid_with_key(token, key, request.body) for key in keys)
