"""Permisos basados en rol para Django REST Framework y OpenAPI."""
from rest_framework.permissions import BasePermission


class EsCoordinadorPermiso(BasePermission):
    """Permite acceso unicamente a usuarios autenticados con rol Coordinador."""

    message = "Solo el Coordinador Deportivo tiene permiso para acceder a este recurso."

    def has_permission(self, request, view) -> bool:
        usuario = getattr(request, "user", None)
        return bool(
            usuario
            and usuario.is_authenticated
            and getattr(usuario, "activo", False)
            and getattr(usuario, "es_coordinador", False)
        )


class EsEntrenadorPermiso(BasePermission):
    """Permite acceso unicamente a usuarios autenticados con rol Entrenador."""

    message = "Solo los Entrenadores tienen permiso para realizar esta acción."

    def has_permission(self, request, view) -> bool:
        usuario = getattr(request, "user", None)
        return bool(
            usuario
            and usuario.is_authenticated
            and getattr(usuario, "activo", False)
            and getattr(usuario, "es_entrenador", False)
        )


class EsEstudiantePermiso(BasePermission):
    """Permite acceso unicamente a usuarios autenticados con rol Estudiante."""

    message = "Solo los Estudiantes tienen permiso para acceder a este recurso."

    def has_permission(self, request, view) -> bool:
        usuario = getattr(request, "user", None)
        return bool(
            usuario
            and usuario.is_authenticated
            and getattr(usuario, "activo", False)
            and getattr(usuario, "es_estudiante", False)
        )
