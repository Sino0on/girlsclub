import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "insecure-dev-key-change-me")
DEBUG = env_bool("DJANGO_DEBUG", True)

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if h.strip()
]

# Needed for POST requests (checkout form, admin login) to pass Django's
# CSRF origin check when served over HTTPS behind a reverse proxy, e.g.
# CSRF_TRUSTED_ORIGINS=https://girlsclub.ques.kg
CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",")
    if o.strip()
]

# nginx (added separately, in front of this app) is expected to terminate
# TLS and set X-Forwarded-Proto — this tells Django the original request
# was HTTPS so it generates correct URLs and sets secure cookies.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SITE_URL = os.environ.get("SITE_URL", "http://127.0.0.1:8000").rstrip("/")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "event",
    "tickets",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "event.context_processors.site_settings",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

if os.environ.get("POSTGRES_HOST"):
    # Used by docker-compose (see docker-compose.yml's "db" service).
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB", "girlsclub"),
            "USER": os.environ.get("POSTGRES_USER", "girlsclub"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
            "HOST": os.environ.get("POSTGRES_HOST", "db"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        }
    }
else:
    # Plain "python manage.py runserver" outside Docker — no Postgres needed.
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ru"
TIME_ZONE = "Asia/Bishkek"
USE_I18N = True
USE_TZ = True

if not DEBUG:
    # Only meaningful once the site is actually served over HTTPS (via
    # nginx, which must set X-Forwarded-Proto: https — see
    # SECURE_PROXY_SSL_HEADER above — or SECURE_SSL_REDIRECT below will
    # redirect-loop). HSTS is deliberately left off until HTTPS has been
    # confirmed solid for a while — enabling it prematurely can lock
    # browsers out of the site over HTTP for a long time if something
    # about the certificate/proxy breaks.
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Event / ticket config ---
TICKET_PRICE_KGS = int(os.environ.get("TICKET_PRICE_KGS", "2000"))

# --- FreedomPay ---
FREEDOMPAY_TEST_MODE = env_bool("FREEDOMPAY_TEST_MODE", True)
FREEDOMPAY_MERCHANT_ID = os.environ.get("FREEDOMPAY_MERCHANT_ID", "")
FREEDOMPAY_SECRET_KEY = os.environ.get("FREEDOMPAY_SECRET_KEY", "")
FREEDOMPAY_API_URL = os.environ.get(
    "FREEDOMPAY_API_URL", "https://api.freedompay.kz/g2g/payment_page/"
)

# --- Email ---
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.example.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL", "FairyTale Picnic <no-reply@example.com>"
)

# --- Telegram moderator bot ---
# The bot token identifies the bot; the chat ID is the moderator GROUP
# it should post receipts to (add the bot to that group first — group
# chat IDs are negative numbers, e.g. -1001234567890).
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_MODERATOR_CHAT_ID = os.environ.get("TELEGRAM_MODERATOR_CHAT_ID", "")
