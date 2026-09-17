import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    raise ImproperlyConfigured(
        "Set SECRET_KEY in .env. Run python scripts/setup_local.py for local development."
    )
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost,testserver").split(",")
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
if os.getenv("DATABASE_URL"):
    from .database import postgres_database

    DATABASES = {
        "default": postgres_database(
            os.environ["DATABASE_URL"],
            schema=os.getenv("DATABASE_SCHEMA", "vedioos"),
            sslrootcert=os.getenv("POSTGRES_SSLROOTCERT"),
        )
    }
elif os.getenv("POSTGRES_DB"):
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
    if not DEBUG:
        raise ImproperlyConfigured("Production requires PostgreSQL configuration.")
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / ".runtime" / "db.sqlite3",
            "OPTIONS": {"timeout": 20},
        }
    }
AUTH_USER_MODEL = "core.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
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
if not DEBUG and not S3_ENDPOINT_URL.startswith("https://"):
    raise ImproperlyConfigured("Production object storage requires HTTPS.")
