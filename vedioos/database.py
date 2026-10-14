"""Parse a server-only PostgreSQL URL without logging credentials."""

import re
from urllib.parse import parse_qs, unquote, urlsplit

import certifi
from django.core.exceptions import ImproperlyConfigured


def postgres_database(url, schema="vedioos", sslrootcert=None, conn_max_age=0):
    try:
        parsed = urlsplit(url)
        port = parsed.port or 5432
    except ValueError:
        raise ImproperlyConfigured("DATABASE_URL is malformed; check URL encoding.") from None
    if (
        parsed.scheme not in ["postgres", "postgresql"]
        or not parsed.hostname
        or not parsed.username
        or not parsed.password
    ):
        raise ImproperlyConfigured("DATABASE_URL must be a complete PostgreSQL connection URL.")
    if parsed.fragment or not parsed.path.strip("/"):
        raise ImproperlyConfigured("DATABASE_URL must include a database name and URL-encoded credentials.")
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", schema) or schema in ["public", "auth", "storage"]:
        raise ImproperlyConfigured("DATABASE_SCHEMA must be a dedicated private application schema.")
    query = parse_qs(parsed.query)
    if query.get("sslmode", ["verify-full"])[-1] not in ["require", "verify-ca", "verify-full"]:
        raise ImproperlyConfigured("An encrypted PostgreSQL connection is required.")
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(parsed.path.lstrip("/")),
        "USER": unquote(parsed.username),
        "PASSWORD": unquote(parsed.password),
        "HOST": parsed.hostname,
        "PORT": port,
        # The shared Supabase session-pooler role has a deliberately small
        # connection allowance. Closing connections after each request keeps
        # several developer previews from exhausting that shared allowance.
        # A deployment with a right-sized pool may opt into persistence.
        "CONN_MAX_AGE": conn_max_age,
        "CONN_HEALTH_CHECKS": True,
        "DISABLE_SERVER_SIDE_CURSORS": True,
        "OPTIONS": {
            "sslmode": "verify-full",
            "sslrootcert": sslrootcert or certifi.where(),
            "connect_timeout": 10,
            "prepare_threshold": None,
            "options": f"-c search_path={schema} -c statement_timeout=30000",
        },
    }
