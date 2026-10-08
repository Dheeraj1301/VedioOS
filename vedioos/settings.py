import os
from pathlib import Path
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
ISOLATED_SQLITE_SETTINGS = os.getenv("DJANGO_SETTINGS_MODULE") in {
    "vedioos.local_settings",
    "vedioos.test_settings",
}
DEBUG = (
    os.getenv("DJANGO_SETTINGS_MODULE") == "vedioos.local_settings"
    or os.getenv("DEBUG", "false").lower() == "true"
)
SUPABASE_PROJECT_REF = os.getenv("SUPABASE_PROJECT_REF", "")
SUPABASE_AUTH_URL = os.getenv(
    "SUPABASE_AUTH_URL",
    f"https://{SUPABASE_PROJECT_REF}.supabase.co" if SUPABASE_PROJECT_REF else "",
)
SUPABASE_AUTH_PUBLISHABLE_KEY = os.getenv("SUPABASE_AUTH_PUBLISHABLE_KEY", "")
SUPABASE_AUTH_TIMEOUT_SECONDS = int(os.getenv("SUPABASE_AUTH_TIMEOUT_SECONDS", "10"))
SHARED_PREVIEW_REQUIRED = os.getenv("SHARED_PREVIEW_REQUIRED", "false").lower() == "true"
SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    raise ImproperlyConfigured(
        "Set SECRET_KEY in .env. Run python scripts/setup_local.py for local development."
    )
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost,testserver").split(",")
CSRF_TRUSTED_ORIGINS = [
    origin.strip() for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if origin.strip()
]
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "operations",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.PrivateResponseMiddleware",
]
ROOT_URLCONF = "vedioos.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context.navigation",
            ]
        },
    }
]
WSGI_APPLICATION = "vedioos.wsgi.application"
if os.getenv("DATABASE_URL") and not ISOLATED_SQLITE_SETTINGS:
    from .database import postgres_database

    DATABASES = {
        "default": postgres_database(
            os.environ["DATABASE_URL"],
            schema=os.getenv("DATABASE_SCHEMA", "vedioos"),
            sslrootcert=os.getenv("POSTGRES_SSLROOTCERT"),
        )
    }
elif os.getenv("POSTGRES_DB") and not ISOLATED_SQLITE_SETTINGS:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ["POSTGRES_DB"],
            "USER": os.environ["POSTGRES_USER"],
            "PASSWORD": os.environ["POSTGRES_PASSWORD"],
            "HOST": os.getenv("POSTGRES_HOST", "127.0.0.1"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
        }
    }
else:
    if not DEBUG and not ISOLATED_SQLITE_SETTINGS:
        raise ImproperlyConfigured("Production requires PostgreSQL configuration.")
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / ".runtime" / "db.sqlite3",
            "OPTIONS": {"timeout": 20},
        }
    }
if SHARED_PREVIEW_REQUIRED and not ISOLATED_SQLITE_SETTINGS:
    database_url = os.getenv("DATABASE_URL", "")
    parsed_database_url = urlparse(database_url)
    identity = f"{parsed_database_url.username or ''}@{parsed_database_url.hostname or ''}"
    if not database_url or not SUPABASE_PROJECT_REF or SUPABASE_PROJECT_REF not in identity:
        raise ImproperlyConfigured(
            "SHARED_PREVIEW_REQUIRED needs DATABASE_URL for the configured SUPABASE_PROJECT_REF."
        )
    if os.getenv("DATABASE_SCHEMA", "vedioos") != "vedioos":
        raise ImproperlyConfigured("Shared previews must use the private vedioos schema.")
    parsed_auth_url = urlparse(SUPABASE_AUTH_URL)
    if (
        parsed_auth_url.scheme != "https"
        or parsed_auth_url.hostname != f"{SUPABASE_PROJECT_REF}.supabase.co"
        or not SUPABASE_AUTH_PUBLISHABLE_KEY
    ):
        raise ImproperlyConfigured(
            "SHARED_PREVIEW_REQUIRED needs the selected project's Supabase Auth URL and publishable key."
        )
AUTH_USER_MODEL = "core.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "core.passwords.PasswordCompositionValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGIN_URL = "/login/"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 0 if DEBUG else 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_REFERRER_POLICY = "same-origin"
SESSION_COOKIE_AGE = 43200
SESSION_SAVE_EVERY_REQUEST = False
TIME_ZONE = "UTC"
USE_TZ = True
LANGUAGE_CODE = "en-us"
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "VedioOS <no-reply@localhost>")
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "true").lower() == "true"
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "false").lower() == "true"
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "10"))
if EMAIL_USE_TLS and EMAIL_USE_SSL:
    raise ImproperlyConfigured("EMAIL_USE_TLS and EMAIL_USE_SSL cannot both be enabled.")
NOTIFICATION_EMAIL_ENABLED = os.getenv("NOTIFICATION_EMAIL_ENABLED", "false").lower() == "true"
NOTIFICATION_DELIVERY_MAX_ATTEMPTS = int(os.getenv("NOTIFICATION_DELIVERY_MAX_ATTEMPTS", "5"))
DATA_UPLOAD_MAX_MEMORY_SIZE = 262144
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "http://127.0.0.1:9000")
S3_REGION = os.getenv("S3_REGION", "us-east-1")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "")
S3_BUCKET = os.getenv("S3_BUCKET", "vedioos-private")
UPLOAD_TTL_SECONDS = int(os.getenv("UPLOAD_TTL_SECONDS", "900"))
DOWNLOAD_TTL_SECONDS = int(os.getenv("DOWNLOAD_TTL_SECONDS", "60"))
PAYMENT_MODE = os.getenv("PAYMENT_MODE", "disabled")
PAYOUT_MODE = os.getenv("PAYOUT_MODE", "disabled")
if PAYOUT_MODE not in {"disabled", "sandbox"} or (PAYOUT_MODE == "sandbox" and not DEBUG):
    raise ImproperlyConfigured("Only disabled payouts or an explicitly enabled DEBUG sandbox are supported.")
SANDBOX_PAYMENT_SECRET = os.getenv("SANDBOX_PAYMENT_SECRET", "")
if PAYMENT_MODE not in {"disabled", "sandbox"} or (PAYMENT_MODE == "sandbox" and not DEBUG):
    raise ImproperlyConfigured("Only disabled payments or an explicitly enabled DEBUG sandbox are supported.")
if not DEBUG and not ISOLATED_SQLITE_SETTINGS and not S3_ENDPOINT_URL.startswith("https://"):
    raise ImproperlyConfigured("Production object storage requires HTTPS.")
