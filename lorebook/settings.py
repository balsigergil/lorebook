"""
Django settings for lorebook project.

Every deployment-specific value is read from the environment (see .env.example).

For more information on this file, see
https://docs.djangoproject.com/en/6.1/topics/settings/
"""

import os
import sys
from pathlib import Path

from django.utils.translation import gettext_lazy as _
from dotenv import load_dotenv

load_dotenv()


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

TESTING = "pytest" in sys.modules or (len(sys.argv) > 1 and sys.argv[1] == "test")

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env_bool("DJANGO_DEBUG")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")

# Application definition

INSTALLED_APPS = [
    "apps.core.apps.CoreConfig",
    "apps.access.apps.AccessConfig",
    "apps.i18n.apps.I18nConfig",
    "apps.content.apps.ContentConfig",
    "apps.media.apps.MediaConfig",
    "apps.search.apps.SearchConfig",
    "apps.comments.apps.CommentsConfig",
    "apps.analytics.apps.AnalyticsConfig",
    "apps.portal.apps.PortalConfig",
    "apps.editor.apps.EditorConfig",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "django.forms",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.openid_connect",
    "django_tasks_db",
    "ninja",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "apps.core.middleware.PortalHostMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "lorebook.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.lorebook",
            ],
        },
    },
]

WSGI_APPLICATION = "lorebook.wsgi.application"
ASGI_APPLICATION = "lorebook.asgi.application"


# Database
# https://docs.djangoproject.com/en/6.1/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST"),
        "PORT": os.getenv("DB_PORT", "5432"),
        "OPTIONS": {
            "pool": not TESTING,
        },
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Cache
# PostgreSQL holds every piece of shared state; the cache only keeps
# short-lived, per-process values (site settings, rotating salts).

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Background tasks: Django's Tasks API backed by the PostgreSQL queue.
# The worker container runs `manage.py db_worker`.

TASKS = {
    "default": {
        "BACKEND": (
            "django.tasks.backends.immediate.ImmediateBackend"
            if TESTING or env_bool("LOREBOOK_TASKS_IMMEDIATE")
            else "django_tasks_db.DatabaseBackend"
        ),
    }
}

# Authentication

AUTH_USER_MODEL = "access.User"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

LOGIN_URL = "account_login"
LOGIN_REDIRECT_URL = "/internal/"
LOGOUT_REDIRECT_URL = "/"

ACCOUNT_ADAPTER = "apps.access.adapters.AccountAdapter"
SOCIALACCOUNT_ADAPTER = "apps.access.adapters.SocialAccountAdapter"
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_LOGOUT_ON_GET = False
ACCOUNT_SESSION_REMEMBER = True
ACCOUNT_DEFAULT_HTTP_PROTOCOL = os.getenv("LOREBOOK_HTTP_PROTOCOL", "http")
SOCIALACCOUNT_LOGIN_ON_GET = False
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True

# Generic OpenID Connect (Google Workspace, Microsoft Entra, Keycloak…).
# Configure one provider through the environment; leave OIDC_CLIENT_ID empty
# to disable it.
LOREBOOK_OIDC_ALLOW_SIGNUP = env_bool("OIDC_ALLOW_SIGNUP")
SOCIALACCOUNT_PROVIDERS = {"openid_connect": {"APPS": []}}
if os.getenv("OIDC_CLIENT_ID"):
    SOCIALACCOUNT_PROVIDERS["openid_connect"]["APPS"].append(
        {
            "provider_id": os.getenv("OIDC_PROVIDER_ID", "oidc"),
            "name": os.getenv("OIDC_NAME", "SSO"),
            "client_id": os.getenv("OIDC_CLIENT_ID"),
            "secret": os.getenv("OIDC_CLIENT_SECRET", ""),
            "settings": {
                "server_url": os.getenv("OIDC_SERVER_URL", ""),
                "token_auth_method": os.getenv("OIDC_TOKEN_AUTH_METHOD", "client_secret_basic"),
            },
        }
    )

# Password validation
# https://docs.djangoproject.com/en/6.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]
if TESTING:
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE")
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE")
# Share the session between the portals when they live on sibling domains,
# e.g. ".exemple.ch" for docs.exemple.ch, kb.exemple.ch and edit.exemple.ch.
SESSION_COOKIE_DOMAIN = os.getenv("DJANGO_SESSION_COOKIE_DOMAIN") or None
CSRF_COOKIE_DOMAIN = SESSION_COOKIE_DOMAIN
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT")
SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_SECURE_HSTS_SECONDS", "0"))
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
if env_bool("DJANGO_BEHIND_PROXY"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True

# Internationalization
# https://docs.djangoproject.com/en/6.1/topics/i18n/
# LANGUAGES lists the languages of the interface. Content languages are
# enabled separately, in the administration (apps.i18n.Language).

LANGUAGE_CODE = os.getenv("LOREBOOK_LANGUAGE_CODE", "en")

LANGUAGES = [
    ("en", _("English")),
    ("fr", _("French")),
    ("de", _("German")),
    ("it", _("Italian")),
]

LOCALE_PATHS = [BASE_DIR / "locale"]

TIME_ZONE = os.getenv("LOREBOOK_TIME_ZONE", "Europe/Zurich")

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.1/howto/static-files/

STATIC_URL = "static/"
STATICFILES_DIRS = [
    ("lorebook", BASE_DIR / "dist"),
]
STATIC_ROOT = BASE_DIR / "static"

# Load the assets from the Vite dev server (npm run dev) instead of the build.
VITE_DEV_SERVER = env_bool("LOREBOOK_VITE_DEV", DEBUG)
VITE_DEV_SERVER_URL = os.getenv("LOREBOOK_VITE_DEV_URL", "http://localhost:5173/static/lorebook")

# Media files. Local disk by default; any S3-compatible storage when
# LOREBOOK_MEDIA_STORAGE=s3. Files are always served through Django, which
# checks the reader's rights before handing them out.

MEDIA_ROOT = Path(os.getenv("LOREBOOK_MEDIA_ROOT", BASE_DIR / "uploads"))
MEDIA_MAX_UPLOAD_SIZE = int(os.getenv("LOREBOOK_MEDIA_MAX_UPLOAD_SIZE", 20 * 1024 * 1024))

if os.getenv("LOREBOOK_MEDIA_STORAGE", "local") == "s3":
    MEDIA_STORAGE = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "endpoint_url": os.getenv("S3_ENDPOINT_URL") or None,
            "bucket_name": os.getenv("S3_BUCKET_NAME"),
            "access_key": os.getenv("S3_ACCESS_KEY_ID"),
            "secret_key": os.getenv("S3_SECRET_ACCESS_KEY"),
            "region_name": os.getenv("S3_REGION_NAME") or None,
            "default_acl": "private",
            "querystring_auth": True,
            "file_overwrite": False,
        },
    }
else:
    MEDIA_STORAGE = {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": MEDIA_ROOT},
    }

STORAGES = {
    "default": MEDIA_STORAGE,
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG or TESTING
            else "whitenoise.storage.CompressedStaticFilesStorage"
        ),
    },
}

# Email
# https://docs.djangoproject.com/en/6.1/topics/email/#topic-email-configuration

email_port = os.getenv("EMAIL_PORT")
MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
        "OPTIONS": {
            "host": os.getenv("EMAIL_HOST"),
            # Without a port, the backend picks one from use_ssl / use_tls.
            "port": int(email_port) if email_port else None,
            "use_tls": env_bool("EMAIL_USE_TLS"),
            "use_ssl": env_bool("EMAIL_USE_SSL"),
            "username": os.getenv("EMAIL_HOST_USER", ""),
            "password": os.getenv("EMAIL_HOST_PASSWORD", ""),
        },
    },
}
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "Lorebook <lorebook@localhost>")
SERVER_EMAIL = os.getenv("SERVER_EMAIL", DEFAULT_FROM_EMAIL)

# Forms
FORM_RENDERER = "apps.core.forms.LoreFormRenderer"

# Lorebook

# Port adapters for the external boundaries.
LOREBOOK_SEARCH_BACKEND = os.getenv(
    "LOREBOOK_SEARCH_BACKEND", "apps.search.backends.postgres.PostgresSearchBackend"
)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.getenv("LOREBOOK_LOG_LEVEL", "INFO")},
}
