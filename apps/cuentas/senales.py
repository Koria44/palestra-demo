"""Senales de autenticacion para trazabilidad en RegistroAuditoria y ultimo_acceso."""
from typing import Any
from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.dispatch import receiver
from django.http import HttpRequest
from django.utils import timezone
from apps.auditoria.models import registrar_evento_auditoria


@receiver(user_logged_in)
def al_iniciar_sesion(
    sender: Any, request: HttpRequest | None, user: Any, **kwargs: Any
) -> None:
    """Actualiza ultimo_acceso y registra el inicio de sesion en la bitacora."""
    user.ultimo_acceso = timezone.now()
    user.save(update_fields=["ultimo_acceso", "actualizado_en"])
    registrar_evento_auditoria(
        usuario=user,
        accion="inicio_sesion_exitoso",
        entidad="Usuario",
        identificador=str(user.id),
        request=request,
        detalle={"rol": getattr(user, "rol", ""), "correo": getattr(user, "email", "")},
    )


@receiver(user_logged_out)
def al_cerrar_sesion(
    sender: Any, request: HttpRequest | None, user: Any, **kwargs: Any
) -> None:
    """Registra el cierre de sesion en la bitacora."""
    if user and getattr(user, "is_authenticated", False):
        registrar_evento_auditoria(
            usuario=user,
            accion="cierre_sesion",
            entidad="Usuario",
            identificador=str(user.id),
            request=request,
            detalle={"correo": getattr(user, "email", "")},
        )


@receiver(user_login_failed)
def al_fallar_inicio_sesion(
    sender: Any, credentials: dict[str, Any], request: HttpRequest | None, **kwargs: Any
) -> None:
    """
    Registra intentos fallidos de inicio de sesion sin almacenar jamas la contrasena.
    """
    identificador = str(credentials.get("username", ""))[:80]
    registrar_evento_auditoria(
        usuario=None,
        accion="inicio_sesion_fallido",
        entidad="Usuario",
        identificador=identificador,
        request=request,
        detalle={"identificador_intentado": identificador},
    )
