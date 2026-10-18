"""Django settings for SmallCompanyRegister.

Every value that differs between installations is read from an environment
variable prefixed with ``SCR_``. See ``.env.example`` for the full list.
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _

from config.plugins import enabled_apps

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


DEBUG = env_bool("SCR_DEBUG")

SECRET_KEY = os.environ.get("SCR_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("Set SCR_SECRET_KEY, or SCR_DEBUG=true for local development.")
    SECRET_KEY = "insecure-development-key"
elif not DEBUG and SECRET_KEY in {"change-me", "insecure-development-key"}:
    # The key signs sessions and password resets; a published one lets anyone forge them.
    raise ImproperlyConfigured("SCR_SECRET_KEY is still the example value; generate a new one.")

ALLOWED_HOSTS = env_list("SCR_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("SCR_CSRF_TRUSTED_ORIGINS")

# All persistent state (databases, uploads) lives in one directory, so a
# backup or a Docker volume only has to cover this path.
DATA_DIR = Path(os.environ.get("SCR_DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "allauth",
    "allauth.account",
    "allauth.mfa",
    "auditlog",
    "huey.contrib.djhuey",
    "apps.core",
    "apps.accounts",
    "apps.register",
    "apps.backups",
    "apps.readings",
    "apps.selfservice",
    "apps.messaging",
    "apps.plugins",
]

# Plugins: installed packages that are Django apps, enabled by name (see
# docs/plugins.md). They come last, so they can override templates only by
# their own names and never replace the app's.
PLUGINS = env_list("SCR_PLUGINS")
PLUGIN_APPS = enabled_apps(PLUGINS)
INSTALLED_APPS += list(PLUGIN_APPS.values())

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "auditlog.middleware.AuditlogMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "apps.accounts.middleware.RequireStaffTwoFactorMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.NoIndexMiddleware",
]

ROOT_URLCONF = "config.urls"

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
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Login, two-factor and password pages come from django-allauth. Accounts are
# created by an admin under Settings; nobody can sign up on their own.
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
LOGIN_URL = "account_login"
LOGIN_REDIRECT_URL = "register:unit_list"
ACCOUNT_LOGOUT_REDIRECT_URL = "account_login"
ACCOUNT_ADAPTER = "apps.accounts.adapter.AccountAdapter"
ACCOUNT_LOGIN_METHODS = {"username"}
ACCOUNT_SIGNUP_FIELDS = ["username*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "none"
MFA_ADAPTER = "apps.accounts.adapter.MFAAdapter"
MFA_SUPPORTED_TYPES = ["totp", "recovery_codes"]
MFA_TOTP_ISSUER = "Small Company Register"

# The audit log records who changed or viewed register data. Changes are
# stored as JSON so custom field values keep their structure.
AUDITLOG_STORE_JSON_CHANGES = True
# Store the name of a linked record (e.g. the unit type) rather than its id.
AUDITLOG_USE_FK_STRING_REPRESENTATION = True

# SQLite in WAL mode lets the web app and the worker read while one writes.
# IMMEDIATE transactions take the write lock up front, which avoids
# "database is locked" errors when two processes write at once.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / "db.sqlite3",
        "OPTIONS": {
            "transaction_mode": "IMMEDIATE",
            "timeout": 20,
            "init_command": (
                "PRAGMA journal_mode=WAL;"
                "PRAGMA synchronous=NORMAL;"
                "PRAGMA foreign_keys=ON;"
                "PRAGMA busy_timeout=5000;"
            ),
        },
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "sv"
LANGUAGES = [
    ("sv", _("Swedish")),
    ("en", _("English")),
]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = os.environ.get("SCR_TIME_ZONE", "Europe/Helsinki")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
MEDIA_ROOT = DATA_DIR / "media"
MEDIA_URL = "media/"

# Background jobs run in a separate worker process (`manage.py run_huey`)
# and keep their queue in its own SQLite file next to the main database.
HUEY = {
    "huey_class": "huey.SqliteHuey",
    "name": "smallcompanyregister",
    "filename": str(DATA_DIR / "huey.sqlite3"),
    "immediate": env_bool("SCR_HUEY_IMMEDIATE"),
    # Scheduled jobs (like the nightly backup) run at local time, not UTC.
    "utc": False,
}

# Backups: a consistent copy of the database plus media, kept locally and,
# when a remote is set, encrypted and uploaded with rclone. See README.
BACKUP = {
    "dir": Path(os.environ.get("SCR_BACKUP_DIR") or DATA_DIR / "backups"),
    "keep": int(os.environ.get("SCR_BACKUP_KEEP") or 14),
    "time": os.environ.get("SCR_BACKUP_TIME") or "02:30",
    "remote_type": os.environ.get("SCR_BACKUP_REMOTE_TYPE", "").strip().lower(),
    "remote_path": os.environ.get("SCR_BACKUP_REMOTE_PATH", ""),
    "encryption_password": os.environ.get("SCR_BACKUP_ENCRYPTION_PASSWORD", ""),
    "s3_provider": os.environ.get("SCR_BACKUP_S3_PROVIDER") or "Other",
    "s3_endpoint": os.environ.get("SCR_BACKUP_S3_ENDPOINT", ""),
    "s3_region": os.environ.get("SCR_BACKUP_S3_REGION", ""),
    "s3_access_key_id": os.environ.get("SCR_BACKUP_S3_ACCESS_KEY_ID", ""),
    "s3_secret_access_key": os.environ.get("SCR_BACKUP_S3_SECRET_ACCESS_KEY", ""),
    "host": os.environ.get("SCR_BACKUP_HOST", ""),
    "port": os.environ.get("SCR_BACKUP_PORT", ""),
    "user": os.environ.get("SCR_BACKUP_USER", ""),
    "password": os.environ.get("SCR_BACKUP_PASSWORD", ""),
    "sftp_key_file": os.environ.get("SCR_BACKUP_SFTP_KEY_FILE", ""),
}

# The address members and staff use, for links in letters, SMS and email.
_domain = os.environ.get("SCR_DOMAIN", "").strip()
BASE_URL = (
    os.environ.get("SCR_BASE_URL")
    or (f"https://{_domain}" if _domain and _domain != "localhost" else "http://localhost:8000")
).rstrip("/")

# Member self-service links: valid until the reading round closes, or this
# many days when the link is not for a round.
SELF_SERVICE_LINK_DAYS = int(os.environ.get("SCR_SELF_SERVICE_LINK_DAYS") or 30)

# Rate limits and other short-lived counters, shared by all web processes
# through files in the data directory (no cache server needed).
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": str(DATA_DIR / "cache"),
    }
}

# Caddy puts the visitor's address in X-Forwarded-For. Only trust it behind
# a proxy that sets it, or anyone could pretend to be someone else.
TRUST_X_FORWARDED_FOR = env_bool("SCR_TRUST_X_FORWARDED_FOR")
# The same for allauth's login and two-factor rate limits: without it every
# visitor shares the proxy's address, so one person's failed logins would lock
# out everyone.
ALLAUTH_TRUSTED_PROXY_COUNT = 1 if TRUST_X_FORWARDED_FOR else 0

# Email: SMTP when SCR_EMAIL_HOST is set, the console in development, or
# none (links then go by SMS or letter). See README, "Email and SMS".
EMAIL_HOST = os.environ.get("SCR_EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("SCR_EMAIL_PORT") or 587)
EMAIL_HOST_USER = os.environ.get("SCR_EMAIL_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("SCR_EMAIL_PASSWORD", "")
EMAIL_USE_TLS = env_bool("SCR_EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env_bool("SCR_EMAIL_USE_SSL")
if EMAIL_USE_SSL:
    EMAIL_USE_TLS = False
EMAIL_TIMEOUT = 30
DEFAULT_FROM_EMAIL = os.environ.get("SCR_EMAIL_FROM") or "register@localhost"
_email_backend = os.environ.get("SCR_EMAIL_BACKEND", "").strip().lower() or (
    "smtp" if EMAIL_HOST else ("console" if DEBUG else "none")
)
EMAIL_BACKEND = {
    "smtp": "django.core.mail.backends.smtp.EmailBackend",
    "console": "django.core.mail.backends.console.EmailBackend",
}.get(_email_backend, "django.core.mail.backends.dummy.EmailBackend")

_elks_user = os.environ.get("SCR_ELKS_API_USER", "")
_reminder_days = os.environ.get("SCR_READING_REMINDER_DAYS", "").strip()
MESSAGING = {
    # Names in apps.messaging.registry; empty means the channel is not set up.
    "email_provider": "" if _email_backend == "none" else "django",
    "sms_provider": os.environ.get("SCR_SMS_PROVIDER", "").strip().lower()
    or ("46elks" if _elks_user else ("console" if DEBUG else "")),
    "email_domain": DEFAULT_FROM_EMAIL.rpartition("@")[2] or "localhost",
    "sms_sender": os.environ.get("SCR_SMS_SENDER", "") or "Register",
    "sms_country_code": (os.environ.get("SCR_SMS_COUNTRY_CODE") or "358").lstrip("+"),
    "elks_api_user": _elks_user,
    "elks_api_password": os.environ.get("SCR_ELKS_API_PASSWORD", ""),
    "elks_dry_run": env_bool("SCR_ELKS_DRY_RUN"),
    # Automatic reminders to units missing a reading, this many days before a
    # round closes. Off unless set.
    "reminder_days_before_close": int(_reminder_days) if _reminder_days else None,
    # Newsletters go out this many emails at a time, with a pause between.
    "newsletter_batch_size": int(os.environ.get("SCR_NEWSLETTER_BATCH_SIZE") or 50),
    "newsletter_pause_seconds": int(os.environ.get("SCR_NEWSLETTER_PAUSE_SECONDS") or 60),
}
if MESSAGING["sms_provider"] == "none":
    MESSAGING["sms_provider"] = ""

# Behind Caddy, the original scheme arrives in X-Forwarded-Proto.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
