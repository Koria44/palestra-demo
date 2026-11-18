"""Configuracion de la aplicacion cuentas."""
from django.apps import AppConfig


class CuentasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.cuentas"
    verbose_name = "Cuentas y Perfiles"

    def ready(self) -> None:
        from . import senales  # noqa: F401
