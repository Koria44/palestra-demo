"""Configuracion estricta para el entorno de produccion de PALESTRA."""
import os
import sys
import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from .base import *  # noqa: F403, F401

DEBUG = False

if not os.environ.get("SECRET_KEY") or len(os.environ.get("SECRET_KEY", "")) < 50:
    raise ImproperlyConfigured(
        "En produccion debe definir una SECRET_KEY aleatoria de al menos 50 caracteres."
    )

es_comando_migracion = any(
    cmd in sys.argv for cmd in ("migrate", "makemigrations", "sqlmigrate")
)
url_bd_directa = os.environ.get("DATABASE_URL_DIRECT", "").strip()
url_bd_pooler = os.environ.get("DATABASE_URL", "").strip()
url_activa = url_bd_directa if (es_comando_migracion and url_bd_directa) else url_bd_pooler

if not url_activa:
    raise ImproperlyConfigured(
        "En produccion es obligatorio configurar DATABASE_URL apuntando a Supabase."
    )

DATABASES = {
    "default": dj_database_url.parse(
        url_activa,
        conn_max_age=0,  # Modo transaccion del pooler de Supabase
        ssl_require=True,
    )
}
DATABASES["default"].setdefault("OPTIONS", {})["sslmode"] = "require"

# Cifrado en transito y cabeceras HTTPS obligatorias (Seccion 6.1.D)
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = 31536000  # 1 ano
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
