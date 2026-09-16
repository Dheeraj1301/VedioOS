"""Explicit local SQLite fallback and source for a controlled cloud data transfer."""

from .settings import *  # noqa: F403
from .settings import BASE_DIR

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / ".runtime" / "db.sqlite3",
        "OPTIONS": {"timeout": 20},
    }
}
