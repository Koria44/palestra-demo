"""Configuracion de la aplicacion auditoria."""
from django.apps import AppConfig


class AuditoriaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.auditoria"
    verbose_name = "Bitacora de Auditoria"
