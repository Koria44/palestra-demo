"""Configuracion de la aplicacion seguimiento."""
from django.apps import AppConfig


class SeguimientoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.seguimiento"
    verbose_name = "Seguimiento de Asistencia y Evaluaciones"
