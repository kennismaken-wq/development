"""
Instellingen voor de klusapp van De Groene M.

Alles wat per omgeving verschilt komt uit environment-variabelen; zie .env.example.
Lokaal draait de app op SQLite, op de VPS op Postgres.
"""

import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_lijst(naam, standaard=""):
    return [deel.strip() for deel in os.environ.get(naam, standaard).split(",") if deel.strip()]


DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"

# In productie moet de sleutel uit de omgeving komen; lokaal mag een vaste
# ontwikkelsleutel, zodat je niet elke keer opnieuw hoeft in te loggen.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "" if not DEBUG else "ontwikkel-sleutel-niet-voor-productie")
if not SECRET_KEY:
    raise RuntimeError("DJANGO_SECRET_KEY ontbreekt. Zet hem in de omgeving van de server.")

ALLOWED_HOSTS = env_lijst("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_lijst("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "medewerkers",
    "klussen",
    "uren",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
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
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": dj_database_url.parse(
        os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
        conn_max_age=600,
    )
}

AUTH_USER_MODEL = "medewerkers.Medewerker"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "inloggen"
LOGIN_REDIRECT_URL = "start"
LOGOUT_REDIRECT_URL = "inloggen"

# Medewerkers vullen hun uren 's avonds in en willen niet elke dag opnieuw
# inloggen; twee weken sessieduur, verlengd bij elk bezoek.
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14
SESSION_SAVE_EVERY_REQUEST = True

LANGUAGE_CODE = "nl-nl"
TIME_ZONE = "Europe/Amsterdam"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "media/"
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", BASE_DIR / "media"))

# Geüploade bestanden worden niet als statische map opengezet: klusfoto's en
# klusdossiers staan niet op een openbaar adres. Ze gaan langs een view die
# controleert of iemand is ingelogd (klussen.views.media_bestand).
#
# Dat kost Django-tijd per bestand. Voor zes medewerkers is dat prima. Zodra
# nginx ervoor staat neemt die het uitleveren over: zet GEBRUIK_X_ACCEL aan en
# geef nginx een interne location op MEDIA_INTERN_PAD die naar MEDIA_ROOT wijst.
# Django doet dan alleen nog de rechtencontrole. Dat is taak T2 in CONTEXT.md.
GEBRUIK_X_ACCEL = os.environ.get("GEBRUIK_X_ACCEL", "0") == "1"
MEDIA_INTERN_PAD = "/intern-media/"

# De manifest-variant hasht bestandsnamen zodat browsers oude CSS niet
# vasthouden. Die vraagt om een collectstatic, dus lokaal draaien we zonder.
STATIC_BACKEND = (
    "django.contrib.staticfiles.storage.StaticFilesStorage"
    if DEBUG
    else "whitenoise.storage.CompressedManifestStaticFilesStorage"
)

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": STATIC_BACKEND},
}

# Foto's komen rechtstreeks van een telefooncamera; die zijn groot.
DATA_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
