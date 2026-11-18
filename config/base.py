"""Configuracion base del sistema PALESTRA (comun a todos los entornos)."""
import os
from pathlib import Path
from dotenv import load_dotenv

RUTA_BASE = Path(__file__).resolve().parent.parent
load_dotenv(RUTA_BASE / ".env")

# Agrega la carpeta apps al path si es necesario, aunque usaremos 'apps.<nombre>'
SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "clave-desarrollo-local-temporal-no-usar-en-produccion-longitud-segura-50-caracteres",
)

claves_anteriores = os.environ.get("SECRET_KEY_FALLBACKS", "").strip()
SECRET_KEY_FALLBACKS = [c.strip() for c in claves_anteriores.split(",") if c.strip()]

DEBUG = os.environ.get("DEBUG", "False").lower() in ("true", "1", "yes")

hosts_permitidos = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1")
ALLOWED_HOSTS = [h.strip() for h in hosts_permitidos.split(",") if h.strip()]

origenes_csrf = os.environ.get(
    "CSRF_TRUSTED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000"
)
CSRF_TRUSTED_ORIGINS = [o.strip() for o in origenes_csrf.split(",") if o.strip()]

# Aplicaciones instaladas
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Terceros
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "axes",
    "csp",
    # Aplicaciones de PALESTRA (nombres en espanol)
    "apps.cuentas",
    "apps.deportes",
    "apps.seguimiento",
    "apps.reportes",
    "apps.auditoria",
    "apps.api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "csp.middleware.CSPMiddleware",
    "axes.middleware.AxesMiddleware",
    "apps.cuentas.middleware.CambioContrasenaObligatorioMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [RUTA_BASE / "templates"],
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

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Modelo de usuario personalizado
AUTH_USER_MODEL = "cuentas.Usuario"

# Backends de autenticacion: Axes primero, luego nuestro backend por correo o RUT
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "apps.cuentas.backends.AutenticacionCorreoORutBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# Hash de contrasenas con Argon2id como algoritmo principal (Seccion 6.1.A)
ARGON2_MEMORIA_KIB = int(os.environ.get("ARGON2_MEMORIA_KIB", "19456"))
ARGON2_ITERACIONES = int(os.environ.get("ARGON2_ITERACIONES", "2"))
ARGON2_PARALELISMO = int(os.environ.get("ARGON2_PARALELISMO", "1"))

PASSWORD_HASHERS = [
    "config.hashers.Argon2PalestraHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

# Politica de contrasenas: minimo 12 caracteres y validadores en espanol
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
    {
        "NAME": "apps.cuentas.validadores.ValidadorComplejidadContrasena",
    },
]

# Internacionalizacion y formatos locales (Espanol de Chile)
LANGUAGE_CODE = "es-cl"
TIME_ZONE = "America/Santiago"
USE_I18N = True
USE_L10N = True
USE_TZ = True

DATE_FORMAT = "d/m/Y"
DATETIME_FORMAT = "d/m/Y H:i"
SHORT_DATE_FORMAT = "d/m/Y"
SHORT_DATETIME_FORMAT = "d/m/Y H:i"
TIME_FORMAT = "H:i"
DECIMAL_SEPARATOR = ","
THOUSAND_SEPARATOR = "."
USE_THOUSAND_SEPARATOR = True

# Archivos estaticos
STATIC_URL = "/static/"
STATICFILES_DIRS = [RUTA_BASE / "static"]
STATIC_ROOT = RUTA_BASE / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Rutas de autenticacion
LOGIN_URL = "cuentas:iniciar_sesion"
LOGIN_REDIRECT_URL = "cuentas:panel_inicio"
LOGOUT_REDIRECT_URL = "cuentas:iniciar_sesion"

# Seguridad de sesiones y cookies (Seccion 6)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 1800  # 30 minutos de inactividad
SESSION_SAVE_EVERY_REQUEST = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"

# Cabeceras de seguridad
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"

# Content Security Policy estricta (django-csp 4.0+) sin scripts inline
from csp.constants import NONE, SELF  # noqa: E402

CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": [SELF],
        "script-src": [SELF],
        "style-src": [SELF],
        "img-src": [SELF, "data:"],
        "font-src": [SELF],
        "connect-src": [SELF],
        "frame-ancestors": [NONE],
        "base-uri": [SELF],
        "form-action": [SELF],
    }
}

# Configuracion de bloqueo por intentos fallidos (django-axes)
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 0.25  # 15 minutos
AXES_LOCKOUT_PARAMETERS = ["username", "ip_address"]
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = "cuentas/bloqueo_intentos.html"

# Claves de cifrado a nivel de campo (Seccion 6.1.E)
CLAVE_CIFRADO_CAMPOS = os.environ.get(
    "CLAVE_CIFRADO_CAMPOS",
    "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
)
CLAVE_INDICE_CIEGO = os.environ.get(
    "CLAVE_INDICE_CIEGO",
    "clave-hmac-indice-ciego-desarrollo-local-palestra-segura",
)

# Parametros de negocio configurables en un unico lugar
ESCALA_NOTAS_MINIMA = 1.0
ESCALA_NOTAS_MAXIMA = 7.0
ESCALA_NOTAS_APROBACION = 4.0
DIAS_VENTANA_CORRECCION = 7

# Tiempos de expiracion de enlaces de un solo uso
TIEMPO_EXPIRACION_ACTIVACION_SEGUNDOS = int(
    os.environ.get("TIEMPO_EXPIRACION_ACTIVACION_SEGUNDOS", "86400")
)
PASSWORD_RESET_TIMEOUT = int(os.environ.get("PASSWORD_RESET_TIMEOUT", "3600"))

# Configuracion de Django REST Framework y OpenAPI
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "20/minute",
        "user": "120/minute",
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "PALESTRA API - Gestion de Actividades Deportivas Estudiantiles",
    "DESCRIPTION": (
        "API RESTful versionada (/api/v1/) para la gestion de disciplinas deportivas, "
        "inscripciones, sesiones de entrenamiento, asistencia, evaluaciones y reportes."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SERVE_PERMISSIONS": ["apps.api.permisos.EsCoordinadorPermiso"],
}

# Configuracion de correo
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL",
    "PALESTRA Gestion Deportiva <no-responder@palestra.institucion.cl>",
)
