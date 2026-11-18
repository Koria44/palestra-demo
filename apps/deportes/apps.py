"""Configuracion de la aplicacion deportes."""
from django.apps import AppConfig


class DeportesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.deportes"
    verbose_name = "Gestion Deportiva"
