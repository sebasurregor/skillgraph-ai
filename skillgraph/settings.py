"""Configuración de SkillGraph AI.

Lee las variables de entorno desde `.env` (python-dotenv). Ver `.env.example`.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

from skillgraph.seguridad import seguridad_transporte

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _env_bool(nombre, defecto):
    return os.getenv(nombre, str(defecto)).strip().lower() in ("1", "true", "yes", "si", "sí")


def _env_lista(nombre, defecto):
    return [v.strip() for v in os.getenv(nombre, defecto).split(",") if v.strip()]


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "clave-solo-para-desarrollo-local")
DEBUG = _env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = _env_lista("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "rest_framework",
    "GraphCore",
    "cuentas",
    "vacantes",
    "perfiles",
    "matching",
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

ROOT_URLCONF = "skillgraph.urls"

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
            ],
        },
    },
]

WSGI_APPLICATION = "skillgraph.wsgi.application"

# ---- Datos relacionales: SQLite3 a través del ORM ---------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---- Datos de grafo: Neo4j (usado por GraphCore.Neo4jConnection) ------------
NEO4J_CONFIG = {
    "URI": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    "USER": os.getenv("NEO4J_USER", "neo4j"),
    "PASSWORD": os.getenv("NEO4J_PASSWORD", ""),
    "DATABASE": os.getenv("NEO4J_DATABASE", "neo4j"),
}

# ---- Motor de matching (coeficientes versionados) ---------------------------
MATCHING_VERSION = os.getenv("MATCHING_VERSION", "1.0.0")
W_COBERTURA = float(os.getenv("W_COBERTURA", "0.60"))
W_NIVEL = float(os.getenv("W_NIVEL", "0.25"))
W_CENTRALIDAD = float(os.getenv("W_CENTRALIDAD", "0.10"))
W_ADYACENCIA = float(os.getenv("W_ADYACENCIA", "0.05"))

# ---- Cuentas y contraseñas (HU-RNF-001) -------------------------------------
AUTH_USER_MODEL = "cuentas.Usuario"
LOGIN_URL = "cuentas:ingresar"
LOGIN_REDIRECT_URL = "cuentas:inicio"

# bcrypt con factor de costo 12 (2^12 iteraciones). Ver cuentas/hashers.py.
PASSWORD_HASHERS = ["cuentas.hashers.BCryptCosto12PasswordHasher"]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 8}},
]

# ---- Sesión: cierre automático tras 15 minutos de inactividad ---------------
SESSION_COOKIE_AGE = 15 * 60
SESSION_SAVE_EVERY_REQUEST = True   # cada petición reinicia el contador
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

# ---- Transporte: HTTPS obligatorio cuando DEBUG=False -----------------------
globals().update(seguridad_transporte(DEBUG))

# ---- Servicios JSON (Django REST Framework) ---------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
}

# ---- Internacionalización ---------------------------------------------------
LANGUAGE_CODE = "es-co"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True

# ---- Archivos estáticos (WhiteNoise) ----------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

# ---- Registro de eventos ----------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "%(asctime)s %(levelname)s %(name)s - %(message)s"},
    },
    "handlers": {
        "consola": {"class": "logging.StreamHandler", "formatter": "simple"},
        "archivo": {
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "skillgraph.log",
            "formatter": "simple",
            "encoding": "utf-8",
            "delay": True,
        },
    },
    "root": {"handlers": ["consola", "archivo"], "level": "INFO"},
}
