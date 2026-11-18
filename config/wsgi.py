"""Configuracion WSGI para el proyecto PALESTRA."""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.produccion")
application = get_wsgi_application()
