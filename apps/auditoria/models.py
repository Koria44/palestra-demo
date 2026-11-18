"""
Modelo RegistroAuditoria y servicio de registro seguro (Seccion 6 y 7).
Es inmutable desde la interfaz y filtra automaticamente cualquier campo sensible
(contrasenas, tokens, hashes, claves) antes de almacenar el detalle.
"""
import uuid
from typing import Any
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import models
from django.http import HttpRequest


CLAVES_PROHIBIDAS_EN_AUDITORIA = {
    "password",
    "password1",
    "password2",
    "new_password1",
    "new_password2",
    "old_password",
    "contrasena",
    "contrasena_actual",
    "contrasena_nueva",
    "confirmar_contrasena",
    "contrasena_temporal",
    "token",
    "token_activacion",
    "hash_token_activacion",
    "secret",
    "clave",
    "csrfmiddlewaretoken",
}


def sanitizar_detalle_auditoria(detalle: dict[str, Any] | None) -> dict[str, Any]:
    """
    Elimina cualquier clave que coincida o contenga nombres de contrasenas o tokens
    para garantizar que ningun secreto llegue jamas a RegistroAuditoria.
    """
    if not detalle or not isinstance(detalle, dict):
        return {}
    limpio: dict[str, Any] = {}
    for clave, valor in detalle.items():
        clave_min = str(clave).lower()
        if (
            clave_min in CLAVES_PROHIBIDAS_EN_AUDITORIA
            or "password" in clave_min
            or "contrasena" in clave_min
            or "token" in clave_min
            or "secret" in clave_min
        ):
            continue
        if isinstance(valor, dict):
            limpio[clave] = sanitizar_detalle_auditoria(valor)
        else:
            limpio[clave] = valor
    return limpio


def obtener_ip_cliente(request: HttpRequest | None) -> str:
    """Obtiene la direccion IP del cliente a partir de la peticion HTTP."""
    if request is None:
        return "127.0.0.1"
    reenviado = request.META.get("HTTP_X_FORWARDED_FOR")
    if reenviado:
        return reenviado.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "127.0.0.1") or "127.0.0.1"


class RegistroAuditoria(models.Model):
    """
    Bitacora de auditoria y trazabilidad de eventos de seguridad y negocio.
    Inmutable: una vez creado un registro, no permite edicion ni eliminacion.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="Identificador",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="registros_auditoria",
        verbose_name="Usuario",
    )
    accion = models.CharField(
        max_length=80,
        db_index=True,
        verbose_name="Accion",
    )
    entidad = models.CharField(
        max_length=80,
        db_index=True,
        verbose_name="Entidad afectada",
    )
    identificador = models.CharField(
        max_length=120,
        blank=True,
        default="",
        verbose_name="Identificador de entidad",
    )
    fecha = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="Fecha y hora",
    )
    direccion_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="Direccion IP",
    )
    detalle = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Detalle adicional",
    )
    creado_en = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Creado en",
    )
    actualizado_en = models.DateTimeField(
        auto_now=True,
        verbose_name="Actualizado en",
    )

    class Meta:
        db_table = "registro_auditoria"
        verbose_name = "Registro de Auditoria"
        verbose_name_plural = "Registros de Auditoria"
        ordering = ["-fecha"]
        indexes = [
            models.Index(fields=["accion", "fecha"], name="idx_auditoria_accion_fecha"),
            models.Index(fields=["entidad", "fecha"], name="idx_auditoria_entidad_fecha"),
        ]

    def save(self, *args, **kwargs) -> None:
        if not self._state.adding and RegistroAuditoria.objects.filter(pk=self.pk).exists():
            raise PermissionDenied(
                "Los registros de la bitacora de auditoria son inmutables y no pueden modificarse."
            )
        self.detalle = sanitizar_detalle_auditoria(self.detalle)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied(
            "Los registros de la bitacora de auditoria son inmutables y no pueden eliminarse."
        )

    def __str__(self) -> str:
        return f"[{self.fecha:%d/%m/%Y %H:%M}] {self.accion} - {self.entidad} ({self.identificador})"


def registrar_evento_auditoria(
    *,
    usuario: Any = None,
    accion: str,
    entidad: str,
    identificador: str = "",
    request: HttpRequest | None = None,
    direccion_ip: str | None = None,
    detalle: dict[str, Any] | None = None,
) -> RegistroAuditoria:
    """Crea un nuevo registro en la bitacora sanitizando cualquier campo sensible."""
    usuario_valido = (
        usuario if (usuario is not None and getattr(usuario, "is_authenticated", False)) else None
    )
    ip_final = direccion_ip or obtener_ip_cliente(request)
    return RegistroAuditoria.objects.create(
        usuario=usuario_valido,
        accion=accion,
        entidad=entidad,
        identificador=str(identificador or ""),
        direccion_ip=ip_final,
        detalle=sanitizar_detalle_auditoria(detalle),
    )
