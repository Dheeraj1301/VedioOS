"""Explicit local SQLite fallback and source for a controlled cloud data transfer."""

from .settings import *  # noqa: F403
from .settings import BASE_DIR

SUPABASE_AUTH_PASSWORD_LOGIN_ENABLED = False

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / ".runtime" / "db.sqlite3",
        "OPTIONS": {"timeout": 20},
    }
}
