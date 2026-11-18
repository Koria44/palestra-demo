"""Configuracion para el entorno de desarrollo local y pruebas de PALESTRA."""
import os
import sys
import dj_database_url
from .base import *  # noqa: F403, F401

DEBUG = os.environ.get("DEBUG", "True").lower() in ("true", "1", "yes")

# Seleccion de cadena de conexion: si es un comando de migracion usa DATABASE_URL_DIRECT si existe
es_comando_migracion = any(
    cmd in sys.argv for cmd in ("migrate", "makemigrations", "sqlmigrate")
)
url_bd_directa = os.environ.get("DATABASE_URL_DIRECT", "").strip()
url_bd_pooler = os.environ.get("DATABASE_URL", "").strip()
usar_sqlite_local = os.environ.get("USAR_SQLITE_LOCAL", "True").lower() in (
    "true",
    "1",
    "yes",
)

url_activa = url_bd_directa if (es_comando_migracion and url_bd_directa) else url_bd_pooler

if url_activa and not usar_sqlite_local:
    DATABASES = {
        "default": dj_database_url.parse(
            url_activa,
            conn_max_age=0 if not es_comando_migracion else 60,
            ssl_require=True,
        )
    }
    DATABASES["default"].setdefault("OPTIONS", {})["sslmode"] = "require"
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": RUTA_BASE / "db.sqlite3",  # noqa: F405
        }
    }

# En desarrollo sobre HTTP local permitimos probar sesiones; en pruebas verificamos tambien flags
SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "False").lower() in (
    "true",
    "1",
    "yes",
)
CSRF_COOKIE_SECURE = os.environ.get("CSRF_COOKIE_SECURE", "False").lower() in (
    "true",
    "1",
    "yes",
)
