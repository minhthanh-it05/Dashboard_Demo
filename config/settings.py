from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(DJANGO_DEBUG=(bool, False), DEMO_MODE=(bool, True))
if (BASE_DIR / ".env").exists():
    environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.core",
    "apps.accounts",
    "apps.projects",
    "apps.procurement",
    "apps.payments",
    "apps.integrations",
    "apps.sales",
    "apps.finance",
    "apps.dashboard",
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
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.demo_mode",
                "apps.accounts.context_processors.roles",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {"default": env.db("DATABASE_URL")}

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "dashboard:home"
LOGOUT_REDIRECT_URL = "accounts:login"

LANGUAGE_CODE = "vi"
TIME_ZONE = "Asia/Ho_Chi_Minh"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Shows a "sample data" banner on every page (CLAUDE.md §6.7, §12).
DEMO_MODE = env("DEMO_MODE")

# External integrations: "mock" (simulated data, default), "live" or "disabled".
# Live adapters stay unusable until vendor access and schemas are confirmed.
OPLACRM_MODE = env.str("OPLACRM_MODE", default="mock")
OPLACRM_BASE_URL = env.str("OPLACRM_BASE_URL", default="")
OPLACRM_API_TOKEN = env.str("OPLACRM_API_TOKEN", default="")

MISA_MODE = env.str("MISA_MODE", default="mock")
MISA_ACT_BASE_URL = env.str("MISA_ACT_BASE_URL", default="")
MISA_APP_ID = env.str("MISA_APP_ID", default="")
MISA_ACCESS_CODE = env.str("MISA_ACCESS_CODE", default="")
MISA_ORG_COMPANY_CODE = env.str("MISA_ORG_COMPANY_CODE", default="")
# No official MISA rate limit is known; keep a conservative gap between calls.
MISA_MIN_REQUEST_INTERVAL_SECONDS = env.float("MISA_MIN_REQUEST_INTERVAL_SECONDS", default=1.0)

INTEGRATION_HTTP_TIMEOUT_SECONDS = env.int("INTEGRATION_HTTP_TIMEOUT_SECONDS", default=30)

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    # 403/404 are expected (object-level permissions); only log server errors.
    "loggers": {"django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False}},
}
