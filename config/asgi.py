"""Configuracion ASGI para el proyecto PALESTRA."""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.produccion")
application = get_asgi_application()
